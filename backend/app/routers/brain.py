"""认知+决策层 API：融合风险事件 / 预案引擎 / 疏散与通学路径"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai import ontology, plan_engine, route_engine
from ..database import get_db
from ..models import HazardEvent, HazardStatus, PlanActivation
from ..schemas import AlertIn, HazardOut, PlanOut
from ..services.fusion import activate_plan, run_fusion

router = APIRouter(prefix="/api/brain", tags=["认知与决策层"])


# ---------- 融合风险 ----------

@router.get("/hazards", response_model=list[HazardOut])
def list_hazards(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(HazardEvent).order_by(HazardEvent.severity.desc(), HazardEvent.created_at.desc())
    if active_only:
        q = q.filter(HazardEvent.status != HazardStatus.cleared)
    return q.limit(50).all()


@router.post("/hazards/{hazard_id}/advance", response_model=HazardOut)
def advance_hazard(hazard_id: int, db: Session = Depends(get_db)):
    ev = db.get(HazardEvent, hazard_id)
    if not ev:
        raise HTTPException(404, "风险事件不存在")
    if ev.status == HazardStatus.active:
        ev.status = HazardStatus.mitigating
    elif ev.status == HazardStatus.mitigating:
        ev.status = HazardStatus.cleared
        ev.cleared_at = datetime.utcnow()
    else:
        raise HTTPException(400, "该风险已解除")
    db.commit()
    db.refresh(ev)
    return ev


@router.post("/fuse", response_model=list[HazardOut])
def trigger_fusion(db: Session = Depends(get_db)):
    """手动触发一轮本体推理（正常由遥测异常/视觉事件/预警接入自动触发）"""
    return run_fusion(db)


@router.get("/ontology")
def ontology_view():
    """本体 T-Box 视图：风险类层级 + 处置知识（前端可视化用）"""
    return {
        "classes": [
            {"class": c, "path": [c, *ontology.superclasses(c)], **ontology.hazard_info(c)}
            for c in ontology._HAZARD_KB
        ],
        "zones": ontology.ZONES,
    }


# ---------- 预案引擎 ----------

@router.post("/alerts", response_model=PlanOut | None)
def ingest_alert(payload: AlertIn, db: Session = Depends(get_db)):
    """官方预警接入：气象/地震预警标准化入口。命中预案矩阵即切换运行模式。"""
    plan = activate_plan(db, payload.alert_type, payload.alert_level,
                         operator=payload.operator, source=payload.source)
    if plan:
        db.commit()
        db.refresh(plan)
        run_fusion(db)   # 预警本身也是一路 official 模态信号
        return plan
    db.commit()
    return None


@router.get("/plan/current")
def current_plan(db: Session = Depends(get_db)):
    plan = (
        db.query(PlanActivation)
        .filter(PlanActivation.active.is_(True))
        .order_by(PlanActivation.created_at.desc())
        .first()
    )
    if not plan:
        return {"mode": "normal", "mode_label": plan_engine.MODE_LABELS["normal"], "plan": None}
    return {
        "mode": plan.mode,
        "mode_label": plan_engine.MODE_LABELS.get(plan.mode, plan.mode),
        "plan": PlanOut.model_validate(plan).model_dump(),
    }


@router.post("/plan/reset")
def reset_plan(operator: str = "admin", db: Session = Depends(get_db)):
    """应急解除：人工确认后恢复正常运行"""
    n = 0
    for plan in db.query(PlanActivation).filter(PlanActivation.active.is_(True)).all():
        plan.active = False
        plan.ended_at = datetime.utcnow()
        n += 1
    db.commit()
    return {"mode": "normal", "deactivated": n, "operator": operator}


@router.get("/plan/matrix")
def plan_matrix():
    """预警响应矩阵全量视图（预案透明公示）"""
    return plan_engine.matrix_view()


# ---------- 图算法：疏散与通学路径 ----------

@router.get("/routes/evacuation")
def evacuation(db: Session = Depends(get_db)):
    """实时疏散路线：活跃风险区域动态加权后的 Dijkstra 结果"""
    hz = {
        e.zone: e.severity
        for e in db.query(HazardEvent).filter(HazardEvent.status != HazardStatus.cleared).all()
    }
    return {"hazard_zones": hz, "routes": route_engine.evacuation_routes(hz)}


@router.get("/routes/commute")
def commute(db: Session = Depends(get_db)):
    """儿童友好通学路评分（活跃风险实时扣分）"""
    hz = {
        e.zone: e.severity
        for e in db.query(HazardEvent).filter(HazardEvent.status != HazardStatus.cleared).all()
    }
    return route_engine.child_friendly_scores(hz)
