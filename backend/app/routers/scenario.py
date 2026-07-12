"""演示场景注入器：一键回放典型场景，驱动全链路（感知→认知→决策→处置）

场景按"风险类型"命名，不绑定具体日期（校历上暑假/周末的日期不构成在校风险）：
- dismissal_rainstorm 「放学高峰暴雨」：气象橙警 + 水位计越限 + 相机积水事件 + 家长上报 → 融合确认内涝 → 室内避险
- food_incident       「食堂异物事件」：家长食安上报 + 留样柜温度越限 + 后厨违规事件 → 融合确认食安风险
- earthquake          「地震预警」：官方预警单源直通 → 紧急疏散模式 + 实时疏散路线
- air_renovation      「翻新教室空气」：教室甲醛/TVOC 双指标越限 + 六年级家长上报 → 空气质量风险
- illness_cluster     「因病缺勤聚集」：3份独立病假单同症状交叉印证 → 校医/班主任预警（传染病早期信号）
- stair_crowding      「楼梯间拥挤」：楼梯相机人群密度 + 噪音瞬时超限 双模态印证 → 错时分流

注入的信号走与真实设备完全相同的入口逻辑（遥测阈值判定/帧推理/工单分类派单/预警矩阵/请假台账），不走后门。
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.incident_classifier import classify_incident, dispatch
from ..ai.vision_engine import analyze_frame
from ..database import get_db
from ..models import (
    Device,
    Incident,
    IncidentLog,
    IncidentStatus,
    LeaveRequest,
    SensorReading,
    Student,
    VisionEvent,
)
from ..routers.incidents import gen_ticket_no
from ..services.fusion import activate_plan, run_fusion

router = APIRouter(prefix="/api/scenario", tags=["演示场景注入器"])


def _inject_telemetry(db: Session, device_id: str, values: list[float]) -> list[str]:
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(500, f"种子数据缺少设备 {device_id}")
    lines = []
    for v in values:
        anomaly = (
            (device.threshold_high is not None and v >= device.threshold_high)
            or (device.threshold_low is not None and v <= device.threshold_low)
        )
        db.add(SensorReading(device_pk=device.id, metric=device.metric or "value",
                             value=v, is_anomaly=anomaly))
        lines.append(f"IoT遥测 {device_id} {device.metric}={v}{device.unit or ''}"
                     + ("（越限异常）" if anomaly else ""))
    db.flush()
    return lines


def _inject_frame(db: Session, device_id: str, hint: str) -> list[str]:
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(500, f"种子数据缺少相机 {device_id}")
    fake_frame = os.urandom(4096)   # 模拟抽帧内容；走与真实帧相同的推理入口
    events = analyze_frame(fake_frame, device.zone, hint)
    lines = []
    for e in events:
        db.add(VisionEvent(device_pk=device.id, event_type=e["event_type"],
                           confidence=e["confidence"], bbox=e.get("bbox"),
                           snapshot_hash=e.get("snapshot_hash")))
        lines.append(f"边缘AI {device_id} 识别 {e['event_type']}（置信度{e['confidence']}，原始帧已丢弃）")
    db.flush()
    return lines


def _inject_incident(db: Session, description: str, location: str) -> list[str]:
    # 上报人固定为演示家长王女士（按姓名查找，避免依赖种子ID顺序）
    from ..models import User
    reporter = db.query(User).filter(User.name == "王女士").first()
    reporter_id = reporter.id if reporter else 1
    category, confidence = classify_incident(description)
    assignee, priority = dispatch(category, description)
    incident = Incident(
        ticket_no=gen_ticket_no(db), reporter_id=reporter_id,
        description=description, location=location,
        category=category, confidence=confidence,
        status=IncidentStatus.dispatched, assignee=assignee,
        priority=priority, source="scenario",
    )
    db.add(incident)
    db.flush()
    db.add(IncidentLog(incident_id=incident.id, from_status=None,
                       to_status=IncidentStatus.dispatched.value,
                       note=f"场景注入·AI识别[{category.value}]派单{assignee}", operator="scenario"))
    return [f"群众上报 {incident.ticket_no}: {description[:30]}… → [{category.value}] {assignee}"]


def _inject_sick_leaves(db: Session, symptoms: list[str], count: int) -> list[str]:
    """向请假台账注入已批准病假（同班同症状），走与真实请假相同的数据结构"""
    students = (
        db.query(Student).filter(Student.class_name == "六年级1班")
        .order_by(Student.id).limit(count).all()
    )
    if len(students) < count:
        raise HTTPException(500, "种子数据学生档案不足，无法注入缺勤聚集场景")
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    lines = []
    for s in students:
        db.add(LeaveRequest(
            student_id=s.id, start_date=today, end_date=tomorrow, days=2,
            leave_type="sick", symptoms=symptoms,
            note="场景注入·演示数据", status="approved", approved_by="李老师",
        ))
        lines.append(f"请假台账 {s.name}（六年级1班）病假：{'/'.join(symptoms)}（班主任已批准）")
    db.flush()
    return lines


@router.post("/{name}")
def run_scenario(name: str, db: Session = Depends(get_db)):
    timeline: list[str] = []

    if name == "dismissal_rainstorm":
        plan = activate_plan(db, "rainstorm", "orange", operator="scenario-rainstorm", source="official")
        timeline.append("官方预警接入：暴雨橙色预警（放学高峰时段，家长正陆续到校门口）")
        if plan:
            timeline.append(f"预案矩阵命中 → 切换[{plan.mode}]，{len(plan.actions)}项动作，"
                            f"自动执行{sum(1 for a in plan.actions if a.get('auto'))}项")
        timeline += _inject_telemetry(db, "iot-water-eastgate-01", [8, 14, 19, 23])
        timeline += _inject_frame(db, "cam-eastgate-01", "waterlogging")
        timeline += _inject_incident(db, "东门下凹路段积水很深了，孩子马上放学，电动车都推不过去", "东门下凹路段")

    elif name == "food_incident":
        timeline += _inject_incident(db, "孩子说今天食堂饭菜里吃出了异物，粥里有虫，希望学校查一下", "食堂后厨")
        timeline += _inject_telemetry(db, "iot-fridge-canteen-01", [6.5, 9.2, 10.1])
        timeline += _inject_frame(db, "cam-kitchen-01", "kitchen_violation")

    elif name == "earthquake":
        plan = activate_plan(db, "earthquake", "warning", operator="scenario-eew", source="official")
        timeline.append("国家地震预警工程接口：预警信号（S波到达前）")
        if plan:
            timeline.append(f"单源高可信直通 → 切换[{plan.mode}]紧急疏散，广播/家长通知已自动推送")

    elif name == "air_renovation":
        timeline += _inject_telemetry(db, "iot-air-class601-01", [0.06, 0.09, 0.11])
        timeline += _inject_telemetry(db, "iot-tvoc-class601-01", [0.45, 0.68])
        timeline += _inject_incident(db, "暑期刚刷完漆的教室气味刺鼻，孩子说下午头晕，担心甲醛超标", "翻新教室(六年级1班)")

    elif name == "illness_cluster":
        timeline += _inject_sick_leaves(db, ["发热", "咳嗽"], 3)
        timeline.append("请假台账聚合：六年级1班 3天内同症状病假达3例（阈值命中）")

    elif name == "stair_crowding":
        timeline += _inject_frame(db, "cam-stair-g6-01", "stair_crowding")
        timeline += _inject_telemetry(db, "iot-noise-stair-01", [78, 82, 85])
        timeline.append("下课铃后楼梯间双模态印证：视觉人群密度 + 瞬时噪音超限")

    else:
        raise HTTPException(404, "未知场景。可用：dismissal_rainstorm / food_incident / earthquake"
                                 " / air_renovation / illness_cluster / stair_crowding")

    db.commit()
    created = run_fusion(db)
    for h in created:
        timeline.append(f"本体推理确认风险：{h.hazard_class} @ {h.zone}（severity={h.severity}），"
                        f"已按 notifyLevel 分级分众通知")
    return {"scenario": name, "timeline": timeline,
            "hazards_created": [h.id for h in created]}


@router.get("")
def list_scenarios():
    return [
        {"name": "dismissal_rainstorm", "label": "放学高峰暴雨", "desc": "橙警+水位越限+视觉积水+家长上报 → 内涝确认 → 室内避险缓释放学"},
        {"name": "food_incident", "label": "食堂异物事件", "desc": "家长上报+留样柜超温+后厨违规 → 食安风险 → 封存留样送检"},
        {"name": "earthquake", "label": "地震预警", "desc": "官方预警直通 → 紧急疏散 + 实时疏散路线"},
        {"name": "air_renovation", "label": "翻新教室空气", "desc": "甲醛/TVOC双指标越限+家长上报 → 教室停用调换"},
        {"name": "illness_cluster", "label": "因病缺勤聚集", "desc": "同班3天同症状病假≥3例 → 校医/班主任预警（传染病早期信号）"},
        {"name": "stair_crowding", "label": "楼梯间拥挤", "desc": "楼梯相机人群密度+噪音瞬时超限 → 错时分流（踩踏风险防范）"},
    ]
