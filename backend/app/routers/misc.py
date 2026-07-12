"""通用 API：AI 对话路由 / 用户"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.chat_engine import build_reply, detect_intent
from ..database import get_db
from ..models import HazardEvent, HazardStatus, PlanActivation, User
from ..schemas import ChatRequest, ChatResponse, UserOut

router = APIRouter(tags=["通用"])


@router.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """意图识别 + 角色权限 + 随答数据：风险/预案类问题直接携带实时数据返回"""
    intent = detect_intent(payload.role, payload.message)
    data = None
    if intent == "query_hazard":
        rows = (
            db.query(HazardEvent)
            .filter(HazardEvent.status != HazardStatus.cleared)
            .order_by(HazardEvent.severity.desc())
            .limit(5)
            .all()
        )
        data = [
            {"hazard_class": r.hazard_class, "zone": r.zone,
             "severity": r.severity, "suggestion": r.suggestion}
            for r in rows
        ]
    elif intent == "query_plan":
        plan = (
            db.query(PlanActivation)
            .filter(PlanActivation.active.is_(True))
            .order_by(PlanActivation.created_at.desc())
            .first()
        )
        data = {
            "mode": plan.mode if plan else "normal",
            "alert": f"{plan.alert_type}·{plan.alert_level}" if plan else None,
        }
    return ChatResponse(intent=intent, reply=build_reply(intent), data=data)


@router.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()
