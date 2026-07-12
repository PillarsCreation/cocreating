"""AI 引擎 · 潮汐安全风险计算

风险分 = 人流指数×0.4 + 车流指数×0.35 + 历史工单密度×0.25
预警级别：>=70 high, >=45 medium, 其余 low
"""
from sqlalchemy.orm import Session

from ..models import SafetySlot

_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def compute_risk_score(crowd: float, traffic: float, incident_count: int) -> float:
    """综合风险分 0-100"""
    incident_index = min(incident_count * 12, 100)  # 每单历史工单折算12分，封顶100
    score = crowd * 0.4 + traffic * 0.35 + incident_index * 0.25
    return round(min(score, 100), 1)


def risk_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def build_suggestion(zone: str, weekday: int, hour: int, score: float) -> str:
    day = _WEEKDAY_NAMES[weekday]
    level = risk_level(score)
    if level == "high":
        return (
            f"{day}{hour}:00 {zone}为高风险时段（{score}分），建议：护学岗提前15分钟到位、"
            f"启用错峰放学预案、推送家长错峰接送提醒。"
        )
    if level == "medium":
        return f"{day}{hour}:00 {zone}为中风险时段（{score}分），建议安排红门管家巡查值守。"
    return f"{day}{hour}:00 {zone}风险较低（{score}分），常规值守即可。"


def refresh_all_scores(db: Session) -> int:
    """重新计算所有时段风险分（例如工单数据更新后调用）"""
    slots = db.query(SafetySlot).all()
    for slot in slots:
        slot.risk_score = compute_risk_score(
            slot.crowd_index, slot.traffic_index, slot.incident_count
        )
    db.commit()
    return len(slots)


def top_alerts(db: Session, limit: int = 5) -> list[dict]:
    """返回风险最高的时段预警"""
    slots = (
        db.query(SafetySlot)
        .order_by(SafetySlot.risk_score.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "zone": s.zone,
            "weekday": s.weekday,
            "hour": s.hour,
            "risk_score": s.risk_score,
            "level": risk_level(s.risk_score),
            "suggestion": build_suggestion(s.zone, s.weekday, s.hour, s.risk_score),
        }
        for s in slots
    ]
