"""潮汐安全 API：热力图 / 预警 / 错峰接送安排"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.safety_engine import refresh_all_scores, top_alerts
from ..database import get_db
from ..models import PickupSchedule, SafetySlot
from ..schemas import PickupScheduleOut, SafetyAlert, SafetySlotOut

router = APIRouter(prefix="/api/safety", tags=["潮汐安全"])


@router.get("/heatmap", response_model=list[SafetySlotOut])
def heatmap(weekday: int | None = None, db: Session = Depends(get_db)):
    """热力图数据：星期 × 时段 × 区域"""
    q = db.query(SafetySlot)
    if weekday is not None:
        q = q.filter(SafetySlot.weekday == weekday)
    return q.order_by(SafetySlot.weekday, SafetySlot.hour).all()


@router.get("/alerts", response_model=list[SafetyAlert])
def alerts(limit: int = 5, db: Session = Depends(get_db)):
    """风险最高时段的预警建议"""
    return top_alerts(db, limit)


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)):
    """工单数据更新后重算全部风险分"""
    count = refresh_all_scores(db)
    return {"refreshed_slots": count}


@router.get("/pickup", response_model=list[PickupScheduleOut])
def pickup_schedules(
    class_name: str | None = None,
    weekday: int | None = None,
    db: Session = Depends(get_db),
):
    """错峰接送安排：家长按班级查询"""
    q = db.query(PickupSchedule)
    if class_name:
        q = q.filter(PickupSchedule.class_name == class_name)
    if weekday is not None:
        q = q.filter(PickupSchedule.weekday == weekday)
    return q.order_by(PickupSchedule.dismiss_time).all()
