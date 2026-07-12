"""处置层 API：分级分众通知（回执/升级） / 资产台账扫码报修 / 食堂食安闭环"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Asset,
    CanteenSample,
    Device,
    Incident,
    IncidentCategory,
    IncidentLog,
    IncidentStatus,
    Notification,
    NotificationReceipt,
    NotifyLevel,
    SensorReading,
    User,
    UserRole,
)
from ..routers.incidents import gen_ticket_no
from ..schemas import (
    AssetOut,
    AssetReportIn,
    CanteenSampleCreate,
    CanteenSampleOut,
    IncidentOut,
    NotificationCreate,
    NotificationOut,
    ReceiptStats,
)
from ..services.fusion import _fanout_receipts

router = APIRouter(tags=["处置层"])

_ESCALATE_MIN = 15   # 紧急通知超时未读 → 升级补呼


# ---------- 通知中枢 ----------

@router.post("/api/notifications", response_model=NotificationOut, status_code=201)
def create_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    notif = Notification(**payload.model_dump())
    db.add(notif)
    db.flush()
    _fanout_receipts(db, notif)
    db.commit()
    db.refresh(notif)
    return notif


@router.get("/api/notifications/inbox/{user_id}", response_model=list[NotificationOut])
def inbox(user_id: int, db: Session = Depends(get_db)):
    """当前用户收件箱（含已读状态）——定向到人，取代刷微信群"""
    if not db.get(User, user_id):
        raise HTTPException(404, "用户不存在")
    rows = (
        db.query(Notification, NotificationReceipt)
        .join(NotificationReceipt, NotificationReceipt.notification_id == Notification.id)
        .filter(NotificationReceipt.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    out = []
    for notif, receipt in rows:
        item = NotificationOut.model_validate(notif)
        item.read_at = receipt.read_at
        out.append(item)
    return out


@router.post("/api/notifications/{notification_id}/read/{user_id}")
def mark_read(notification_id: int, user_id: int, db: Session = Depends(get_db)):
    receipt = (
        db.query(NotificationReceipt)
        .filter(
            NotificationReceipt.notification_id == notification_id,
            NotificationReceipt.user_id == user_id,
        )
        .first()
    )
    if not receipt:
        raise HTTPException(404, "回执记录不存在")
    if receipt.read_at is None:
        receipt.read_at = datetime.utcnow()
        db.commit()
    return {"read_at": receipt.read_at.isoformat()}


@router.get("/api/notifications/{notification_id}/receipts", response_model=ReceiptStats)
def receipt_stats(notification_id: int, db: Session = Depends(get_db)):
    """回执统计 + 超时未读升级清单（紧急通知15分钟未读列入电话补呼）"""
    notif = db.get(Notification, notification_id)
    if not notif:
        raise HTTPException(404, "通知不存在")
    receipts = (
        db.query(NotificationReceipt, User)
        .join(User, NotificationReceipt.user_id == User.id)
        .filter(NotificationReceipt.notification_id == notification_id)
        .all()
    )
    read = [r for r, _ in receipts if r.read_at is not None]
    escalated = []
    if notif.level == NotifyLevel.emergency:
        deadline = notif.created_at + timedelta(minutes=_ESCALATE_MIN)
        for receipt, user in receipts:
            if receipt.read_at is None and datetime.utcnow() >= deadline:
                receipt.escalated = True
                escalated.append({"user_id": user.id, "name": user.name,
                                  "phone": user.phone or "未登记"})
        db.commit()
    return ReceiptStats(
        notification_id=notification_id,
        total=len(receipts), read=len(read), unread=len(receipts) - len(read),
        escalated=escalated,
    )


# ---------- 资产台账（桌椅/翻新工程） ----------
# 资产管理归口校长（admin）：老师不需要也看不到资产台账；
# 扫码报修（report_asset）不在此限——任何角色发现坏损都可扫码报修。

def _require_admin(db: Session, operator_id: int) -> User:
    op = db.get(User, operator_id)
    if not op or op.role != UserRole.admin:
        raise HTTPException(403, "资产台账仅校方管理员（校长）可见")
    return op


@router.get("/api/assets", response_model=list[AssetOut])
def list_assets(operator_id: int, grade: int | None = None, category: str | None = None,
                db: Session = Depends(get_db)):
    _require_admin(db, operator_id)
    q = db.query(Asset).order_by(Asset.condition, Asset.code)
    if grade is not None:
        q = q.filter(Asset.grade == grade)
    if category:
        q = q.filter(Asset.category == category)
    return q.all()


@router.get("/api/assets/{code}", response_model=AssetOut)
def get_asset(code: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.code == code).first()
    if not asset:
        raise HTTPException(404, "资产码不存在")
    return asset


@router.post("/api/assets/{code}/report", response_model=IncidentOut, status_code=201)
def report_asset(code: str, payload: AssetReportIn, db: Session = Depends(get_db)):
    """扫码报修：资产二维码 → facility 工单（自动带位置与资产引用），报修即降一级成色"""
    asset = db.query(Asset).filter(Asset.code == code).first()
    if not asset:
        raise HTTPException(404, "资产码不存在")
    if not db.get(User, payload.reporter_id):
        raise HTTPException(404, "上报人不存在")

    incident = Incident(
        ticket_no=gen_ticket_no(db),
        reporter_id=payload.reporter_id,
        description=f"[资产报修 {asset.code} {asset.name}] {payload.description}",
        location=asset.location,
        category=IncidentCategory.facility,
        confidence=1.0,
        status=IncidentStatus.dispatched,
        assignee="总务处·后勤维修组",
        priority=2,
        source="asset",
        ref=asset.code,
    )
    db.add(incident)
    db.flush()
    db.add(IncidentLog(
        incident_id=incident.id, from_status=None,
        to_status=IncidentStatus.dispatched.value,
        note=f"扫码报修，资产 {asset.code} 成色 {asset.condition}→{max(asset.condition - 1, 1)}",
        operator="asset-qr",
    ))
    asset.condition = max(asset.condition - 1, 1)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/api/assets-summary")
def assets_summary(operator_id: int, db: Session = Depends(get_db)):
    """按年级汇总资产成色 —— 直接回应六年级家长"硬件被遗忘"的评价（校长专属）"""
    _require_admin(db, operator_id)
    rows = db.query(Asset).all()
    by_grade: dict[int, dict] = {}
    for a in rows:
        g = a.grade or 0
        entry = by_grade.setdefault(g, {"grade": g, "count": 0, "condition_sum": 0, "worst": 5})
        entry["count"] += a.quantity
        entry["condition_sum"] += a.condition * a.quantity
        entry["worst"] = min(entry["worst"], a.condition)
    return sorted(
        (
            {"grade": e["grade"], "count": e["count"],
             "avg_condition": round(e["condition_sum"] / max(e["count"], 1), 2),
             "worst": e["worst"]}
            for e in by_grade.values()
        ),
        key=lambda x: x["avg_condition"],
    )


# ---------- 食堂食安闭环 ----------

@router.post("/api/canteen/samples", response_model=CanteenSampleOut, status_code=201)
def create_sample(payload: CanteenSampleCreate, db: Session = Depends(get_db)):
    if not db.query(Device).filter(Device.device_id == payload.fridge_device_id).first():
        raise HTTPException(404, f"留样柜设备未注册：{payload.fridge_device_id}")
    sample = CanteenSample(**payload.model_dump())
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/api/canteen/samples", response_model=list[CanteenSampleOut])
def list_samples(date: str | None = None, db: Session = Depends(get_db)):
    q = db.query(CanteenSample).order_by(CanteenSample.created_at.desc())
    if date:
        q = q.filter(CanteenSample.date == date)
    return q.limit(100).all()


@router.get("/api/canteen/board")
def canteen_board(db: Session = Depends(get_db)):
    """明厨亮灶公示板：留样合规率 + 冷链温度曲线 + 食安相关工单 → 食安指数（家长可见）"""
    samples = db.query(CanteenSample).order_by(CanteenSample.created_at.desc()).limit(60).all()
    dates = {s.date for s in samples}
    # 合规：每日午餐留样 ≥3 道菜（演示口径）
    compliant_days = sum(
        1 for d in dates
        if sum(1 for s in samples if s.date == d and s.meal == "lunch") >= 3
    )
    sample_rate = round(compliant_days / len(dates), 2) if dates else 0.0

    fridge = db.query(Device).filter(Device.device_id == "iot-fridge-canteen-01").first()
    temps = []
    temp_ok = True
    if fridge:
        readings = (
            db.query(SensorReading)
            .filter(SensorReading.device_pk == fridge.id)
            .order_by(SensorReading.created_at.desc())
            .limit(24)
            .all()
        )
        temps = [
            {"value": r.value, "is_anomaly": r.is_anomaly, "at": r.created_at.isoformat()}
            for r in reversed(readings)
        ]
        temp_ok = not any(r["is_anomaly"] for r in temps[-6:])   # 近6次无越限

    open_food_tickets = (
        db.query(Incident)
        .filter(Incident.category == IncidentCategory.food,
                Incident.status.notin_([IncidentStatus.resolved, IncidentStatus.closed]))
        .count()
    )
    index = round(100 * (0.4 * sample_rate + 0.4 * (1 if temp_ok else 0)
                         + 0.2 * (1 if open_food_tickets == 0 else 0)))
    return {
        "food_safety_index": index,
        "sample_compliance_rate": sample_rate,
        "cold_chain_ok": temp_ok,
        "open_food_tickets": open_food_tickets,
        "fridge_temps": temps,
        "recent_samples": [
            {"date": s.date, "meal": s.meal, "dish": s.dish,
             "weight_g": s.weight_g, "operator": s.operator}
            for s in samples[:10]
        ],
    }
