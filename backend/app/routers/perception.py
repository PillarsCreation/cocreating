"""感知层 API：设备注册表 / IoT 遥测 / 边缘视频事件

遥测入口对应 MQTT 网关：topic redgate/{device_id}/{metric} 的消息由网关 POST 到 /telemetry。
视频入口 /frames 接收边缘相机抽帧，推理后只落结构化事件（原始帧即弃）。
"""
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..ai.vision_engine import analyze_frame
from ..database import get_db
from ..models import Device, SensorReading, VisionEvent
from ..schemas import DeviceOut, TelemetryIn, TelemetryOut, VisionEventOut
from ..services.fusion import run_fusion

router = APIRouter(prefix="/api/perception", tags=["感知层"])

_DEDUP_WINDOW_MIN = 10   # 同设备同类型事件在窗口内合并计数


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.zone, Device.device_id).all()


@router.post("/telemetry", response_model=TelemetryOut, status_code=201)
def ingest_telemetry(payload: TelemetryIn, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if not device:
        raise HTTPException(404, f"设备未注册：{payload.device_id}")

    anomaly = (
        (device.threshold_high is not None and payload.value >= device.threshold_high)
        or (device.threshold_low is not None and payload.value <= device.threshold_low)
    )
    reading = SensorReading(
        device_pk=device.id, metric=payload.metric,
        value=payload.value, is_anomaly=anomaly,
    )
    device.online = True
    db.add(reading)
    db.commit()

    if anomaly:
        run_fusion(db)   # 异常读数触发一轮本体推理

    return TelemetryOut(
        device_id=device.device_id, metric=reading.metric, value=reading.value,
        is_anomaly=anomaly, threshold_high=device.threshold_high,
        created_at=reading.created_at,
    )


@router.get("/telemetry/latest")
def latest_telemetry(db: Session = Depends(get_db)):
    """每台设备最新读数（大屏轮询用）"""
    out = []
    for device in db.query(Device).all():
        r = (
            db.query(SensorReading)
            .filter(SensorReading.device_pk == device.id)
            .order_by(SensorReading.created_at.desc())
            .first()
        )
        out.append({
            "device_id": device.device_id, "name": device.name,
            "dtype": device.dtype.value, "zone": device.zone,
            "metric": device.metric, "unit": device.unit,
            "threshold_high": device.threshold_high,
            "value": r.value if r else None,
            "is_anomaly": r.is_anomaly if r else False,
            "at": r.created_at.isoformat() if r else None,
            "online": device.online,
        })
    return out


@router.post("/frames")
async def ingest_frame(
    device_id: str = Form(...),
    hint: str | None = Form(default=None),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """边缘相机抽帧入口。返回本帧产出的结构化事件；原始帧不落盘。"""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(404, f"相机未注册：{device_id}")

    data = await frame.read()
    events = analyze_frame(data, device.zone, hint)
    stored = []
    window = datetime.utcnow() - timedelta(minutes=_DEDUP_WINDOW_MIN)
    for e in events:
        dup = (
            db.query(VisionEvent)
            .filter(
                VisionEvent.device_pk == device.id,
                VisionEvent.event_type == e["event_type"],
                VisionEvent.last_at >= window,
            )
            .first()
        )
        if dup:
            dup.count += 1
            dup.last_at = datetime.utcnow()
            dup.confidence = max(dup.confidence, e["confidence"])
            stored.append(dup)
        else:
            ve = VisionEvent(
                device_pk=device.id, event_type=e["event_type"],
                confidence=e["confidence"], bbox=e.get("bbox"),
                snapshot_hash=e.get("snapshot_hash"),
            )
            db.add(ve)
            stored.append(ve)
    db.commit()

    if stored:
        run_fusion(db)

    return {
        "device_id": device_id,
        "frame_sha256": hashlib.sha256(data).hexdigest(),
        "frame_bytes_discarded": True,   # 数据安全：原始帧不留存
        "events": [
            {"event_type": s.event_type, "confidence": s.confidence,
             "bbox": s.bbox, "count": s.count}
            for s in stored
        ],
    }


@router.get("/vision-events", response_model=list[VisionEventOut])
def list_vision_events(hours: int = 24, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(VisionEvent, Device)
        .join(Device, VisionEvent.device_pk == Device.id)
        .filter(VisionEvent.last_at >= since)
        .order_by(VisionEvent.last_at.desc())
        .limit(100)
        .all()
    )
    return [
        VisionEventOut(
            id=ev.id, event_type=ev.event_type, confidence=ev.confidence,
            bbox=ev.bbox, snapshot_hash=ev.snapshot_hash, count=ev.count,
            zone=device.zone, device_id=device.device_id, last_at=ev.last_at,
        )
        for ev, device in rows
    ]
