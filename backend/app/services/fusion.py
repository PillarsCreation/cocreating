"""认知-决策-处置 联动服务

run_fusion(db)：汇聚近30分钟四类模态信号（IoT异常读数/视觉事件/群众工单/官方预警）
  → 本体前向链推理 → 融合风险事件入库（同类风险合并更新，不重复告警）
  → 按 notifyLevel 自动生成分级分众通知（含回执名单）
  → severity≥3 且本体建议预案时自动切换运行模式（单调升级）

activate_plan(db, ...)：官方预警/人工/场景注入 → 预案矩阵 → 模式切换 + 动作清单 + 全员通知
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..ai import ontology, plan_engine
from ..models import (
    Device,
    HazardEvent,
    HazardStatus,
    Incident,
    Notification,
    NotificationReceipt,
    NotifyLevel,
    PlanActivation,
    SensorReading,
    User,
    UserRole,
    VisionEvent,
)

_WINDOW_MIN = 30

# 工单类别 → 本体 citizen 模态 key
_CATEGORY_TO_SIGNAL = {
    "traffic": "traffic", "vendor": "vendor", "fire_hazard": "fire_hazard",
    "flood": "flood", "food": "food", "air": "air",
}

# 风险类 → 通知受众角色（学生无账号：通过家长账号、校园广播与班级通知触达）
_HAZARD_AUDIENCE: dict[str, list[str]] = {
    "waterlogging": ["parent", "teacher", "community", "admin"],
    "typhoon_wind": ["parent", "teacher", "admin"],
    "earthquake": ["parent", "teacher", "community", "admin"],
    "food_safety": ["parent", "teacher", "admin"],
    "air_quality": ["parent", "teacher", "admin"],
    "gate_congestion": ["parent", "community", "admin"],
    "fire_channel_blocked": ["community", "admin"],
    "illness_cluster": ["teacher", "admin"],   # 先到校医/班主任，确认后再定向家长
    "stair_crowding": ["teacher", "admin"],
}

_HAZARD_LABELS = {
    "waterlogging": "校门积水内涝", "typhoon_wind": "大风/台风", "earthquake": "地震预警",
    "food_safety": "食堂食品安全", "air_quality": "教室空气质量", "gate_congestion": "校门口拥堵",
    "illegal_parking": "违停", "fire_channel_blocked": "消防通道占用", "noise": "噪音超标",
    "illness_cluster": "因病缺勤聚集", "stair_crowding": "楼梯间人群拥挤",
}


def collect_signals(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or datetime.utcnow()
    since = now - timedelta(minutes=_WINDOW_MIN)
    signals: list[dict] = []

    rows = (
        db.query(SensorReading, Device)
        .join(Device, SensorReading.device_pk == Device.id)
        .filter(SensorReading.is_anomaly.is_(True), SensorReading.created_at >= since)
        .all()
    )
    for reading, device in rows:
        signals.append({
            "modality": "sensor", "key": reading.metric, "value": reading.value,
            "zone": device.zone, "ref": device.device_id, "at": reading.created_at,
        })

    ve_rows = (
        db.query(VisionEvent, Device)
        .join(Device, VisionEvent.device_pk == Device.id)
        .filter(VisionEvent.last_at >= since)
        .all()
    )
    for ev, device in ve_rows:
        signals.append({
            "modality": "vision", "key": ev.event_type, "zone": device.zone,
            "ref": f"{device.device_id}#VE{ev.id}", "at": ev.last_at,
        })

    for inc in db.query(Incident).filter(Incident.created_at >= since).all():
        key = _CATEGORY_TO_SIGNAL.get(inc.category.value)
        if key:
            signals.append({
                "modality": "citizen", "key": key, "zone": inc.location,
                "ref": inc.ticket_no, "at": inc.created_at,
            })

    for plan in db.query(PlanActivation).filter(
        PlanActivation.active.is_(True), PlanActivation.source == "official"
    ).all():
        signals.append({
            "modality": "official", "key": plan.alert_type, "level": plan.alert_level,
            "ref": f"官方预警#{plan.id}", "at": plan.created_at,
        })

    # 请假台账 → 因病缺勤聚集信号：同班3天内同症状≥3例（3份独立家长请假单交叉印证）
    signals.extend(_illness_cluster_signals(db, now))
    return signals


def _illness_cluster_signals(db: Session, now: datetime) -> list[dict]:
    from ..models import LeaveRequest, Student   # 局部导入避免环
    since = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    rows = (
        db.query(LeaveRequest, Student)
        .join(Student, LeaveRequest.student_id == Student.id)
        .filter(LeaveRequest.leave_type == "sick",
                LeaveRequest.status == "approved",
                LeaveRequest.start_date >= since)
        .all()
    )
    counter: dict[tuple[str, str], int] = {}
    for r, s in rows:
        for sym in (r.symptoms or []):
            counter[(s.class_name, sym)] = counter.get((s.class_name, sym), 0) + 1
    return [
        {"modality": "citizen", "key": "illness_cluster", "zone": cls,
         "ref": f"请假台账·{sym}×{n}例", "at": now}
        for (cls, sym), n in counter.items() if n >= 3
    ]


def run_fusion(db: Session, now: datetime | None = None) -> list[HazardEvent]:
    """执行一轮推理。返回本轮新建的风险事件（更新已有事件不重复返回/通知）"""
    now = now or datetime.utcnow()
    fused = ontology.fuse(collect_signals(db, now), now)
    created: list[HazardEvent] = []

    for h in fused:
        existing = (
            db.query(HazardEvent)
            .filter(
                HazardEvent.hazard_class == h["hazard_class"],
                HazardEvent.zone == h["zone"],
                HazardEvent.status != HazardStatus.cleared,
            )
            .first()
        )
        if existing:
            # 同一活跃风险：只在升级时更新并重新通知
            if h["severity"] > existing.severity:
                existing.severity = h["severity"]
                existing.sources = h["sources"]
                existing.inference = h["inference"]
                _notify_hazard(db, existing, h["notify_level"], upgraded=True)
            continue

        event = HazardEvent(
            hazard_class=h["hazard_class"], zone=h["zone"], severity=h["severity"],
            sources=h["sources"], inference=h["inference"], suggestion=h["suggestion"],
        )
        db.add(event)
        db.flush()
        created.append(event)
        _notify_hazard(db, event, h["notify_level"])

        # 严重风险 + 本体给出预案建议 → 自动切换运行模式
        plan = h.get("recommend_plan")
        if plan and h["severity"] >= 3:
            activate_plan(db, plan[0], plan[1], operator="ontology-fusion", source="fusion")

    db.commit()
    return created


def _notify_hazard(db: Session, event: HazardEvent, level: str, upgraded: bool = False) -> None:
    label = _HAZARD_LABELS.get(event.hazard_class, event.hazard_class)
    roles = _HAZARD_AUDIENCE.get(event.hazard_class, ["admin"])
    prefix = "【风险升级】" if upgraded else "【风险确认】"
    notif = Notification(
        title=f"{prefix}{label} @ {event.zone}（{event.severity}级）",
        body=f"{event.suggestion}\n\n—— 推理依据 ——\n{event.inference}",
        level=NotifyLevel(level),
        audience_roles=roles,
        hazard_id=event.id,
        created_by="ontology-fusion",
    )
    db.add(notif)
    db.flush()
    _fanout_receipts(db, notif)


def activate_plan(
    db: Session, alert_type: str, alert_level: str,
    operator: str, source: str = "official",
) -> PlanActivation | None:
    """预警矩阵查询 + 单调升级：新模式保护等级低于当前活跃预案时仅记录不切换"""
    resolved = plan_engine.resolve_plan(alert_type, alert_level)
    if resolved is None:
        return None
    mode, actions = resolved

    current = (
        db.query(PlanActivation)
        .filter(PlanActivation.active.is_(True))
        .order_by(PlanActivation.created_at.desc())
        .first()
    )
    if current and not plan_engine.is_upgrade(current.mode, mode) and current.mode != "normal":
        if source != "manual":   # 人工操作允许显式降级
            return None
    if current:
        current.active = False
        current.ended_at = datetime.utcnow()

    plan = PlanActivation(
        alert_type=alert_type, alert_level=alert_level, mode=mode,
        actions=actions, operator=operator, source=source,
    )
    db.add(plan)
    db.flush()

    auto_done = [a["text"] for a in actions if a.get("auto")]
    notif = Notification(
        title=f"【预案切换】{plan_engine.MODE_LABELS[mode]}（{alert_type}·{alert_level}）",
        body="校园运行模式已切换。\n已自动执行：\n" + "\n".join(f"· {t}" for t in auto_done)
             + "\n\n待责任人确认：\n"
             + "\n".join(f"· {a['text']}（{a['owner']}）" for a in actions if not a.get("auto")),
        level=NotifyLevel.emergency if mode in ("home_study", "evacuate") else NotifyLevel.important,
        audience_roles=["parent", "teacher", "community", "admin"],
        plan_id=plan.id,
        created_by=operator,
    )
    db.add(notif)
    db.flush()
    _fanout_receipts(db, notif)
    return plan


def _fanout_receipts(db: Session, notif: Notification) -> None:
    """为受众生成回执记录（定向到人是超越微信群的关键）"""
    q = db.query(User).filter(User.role.in_([UserRole(r) for r in notif.audience_roles]))
    if notif.audience_class:
        q = q.filter(User.class_name == notif.audience_class)
    for user in q.all():
        db.add(NotificationReceipt(notification_id=notif.id, user_id=user.id))
