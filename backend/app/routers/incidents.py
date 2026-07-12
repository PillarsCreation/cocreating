"""随手拍工单 API：上报 → AI分类 → 自动派单 → 流转 → 统计

v3：工单同时作为本体推理的 citizen 模态信号 —— 创建后触发一轮多模态融合。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..ai.incident_classifier import classify_incident, dispatch
from ..database import get_db
from ..models import Incident, IncidentLog, IncidentStatus, SafetySlot, User
from ..schemas import IncidentCreate, IncidentOut, IncidentStats, IncidentUpdateStatus
from ..services.fusion import run_fusion

router = APIRouter(prefix="/api/incidents", tags=["随手拍工单"])

# 状态机：合法流转路径
_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.reported: {IncidentStatus.dispatched},
    IncidentStatus.dispatched: {IncidentStatus.processing, IncidentStatus.resolved},
    IncidentStatus.processing: {IncidentStatus.resolved},
    IncidentStatus.resolved: {IncidentStatus.closed},
    IncidentStatus.closed: set(),
}


def gen_ticket_no(db: Session) -> str:
    today = datetime.now().strftime("%Y%m%d")
    count = (
        db.query(Incident)
        .filter(Incident.ticket_no.like(f"RG-{today}-%"))
        .count()
    )
    return f"RG-{today}-{count + 1:03d}"


@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    if not db.get(User, payload.reporter_id):
        raise HTTPException(404, "上报人不存在")

    category, confidence = classify_incident(payload.description)
    assignee, priority = dispatch(category, payload.description)

    incident = Incident(
        ticket_no=gen_ticket_no(db),
        reporter_id=payload.reporter_id,
        description=payload.description,
        image_path=payload.image_path,
        location=payload.location,
        category=category,
        confidence=confidence,
        status=IncidentStatus.dispatched,  # 创建即完成AI派单
        assignee=assignee,
        priority=priority,
    )
    db.add(incident)
    db.flush()
    db.add_all([
        IncidentLog(incident_id=incident.id, from_status=None,
                    to_status=IncidentStatus.reported.value, note="用户上报", operator="user"),
        IncidentLog(incident_id=incident.id, from_status=IncidentStatus.reported.value,
                    to_status=IncidentStatus.dispatched.value,
                    note=f"AI识别为[{category.value}]（置信度{confidence}），已派单至{assignee}",
                    operator="ai"),
    ])

    # 联动潮汐安全：该位置对应区域的历史工单数 +1
    slot = db.query(SafetySlot).filter(SafetySlot.zone == payload.location).first()
    if slot:
        slot.incident_count += 1

    db.commit()
    db.refresh(incident)

    # 工单即 citizen 模态信号：与传感器/视频/预警交叉印证
    run_fusion(db)
    return incident


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status: IncidentStatus | None = None,
    source: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(Incident).order_by(Incident.priority, Incident.created_at.desc())
    if status:
        q = q.filter(Incident.status == status)
    if source:
        q = q.filter(Incident.source == source)
    return q.limit(limit).all()


@router.get("/stats", response_model=IncidentStats)
def incident_stats(db: Session = Depends(get_db)):
    total = db.query(Incident).count()
    by_status = dict(
        db.query(Incident.status, func.count()).group_by(Incident.status).all()
    )
    by_category = dict(
        db.query(Incident.category, func.count()).group_by(Incident.category).all()
    )
    by_source = dict(
        db.query(Incident.source, func.count()).group_by(Incident.source).all()
    )
    resolved = (
        db.query(Incident)
        .filter(Incident.resolved_at.isnot(None))
        .all()
    )
    avg_hours = None
    if resolved:
        avg_hours = round(
            sum((i.resolved_at - i.created_at).total_seconds() for i in resolved)
            / len(resolved) / 3600, 2,
        )
    return IncidentStats(
        total=total,
        by_status={k.value: v for k, v in by_status.items()},
        by_category={k.value: v for k, v in by_category.items()},
        by_source=by_source,
        avg_resolve_hours=avg_hours,
    )


@router.get("/{ticket_no}", response_model=IncidentOut)
def get_incident(ticket_no: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.ticket_no == ticket_no).first()
    if not incident:
        raise HTTPException(404, "工单不存在")
    return incident


@router.patch("/{ticket_no}/status", response_model=IncidentOut)
def update_status(
    ticket_no: str, payload: IncidentUpdateStatus, db: Session = Depends(get_db)
):
    incident = db.query(Incident).filter(Incident.ticket_no == ticket_no).first()
    if not incident:
        raise HTTPException(404, "工单不存在")
    if payload.to_status not in _TRANSITIONS[incident.status]:
        raise HTTPException(
            400,
            f"非法流转：{incident.status.value} → {payload.to_status.value}",
        )
    db.add(IncidentLog(
        incident_id=incident.id,
        from_status=incident.status.value,
        to_status=payload.to_status.value,
        note=payload.note,
        operator=payload.operator,
    ))
    incident.status = payload.to_status
    if payload.to_status == IncidentStatus.resolved:
        incident.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(incident)
    return incident
