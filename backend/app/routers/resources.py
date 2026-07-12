"""共享空间与预约 API：检索 / 冲突检测 / 预约流转 / 错峰停车实时空位 / 平急两用视图"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Booking, BookingStatus, CommunityResource, Device, SensorReading, User, UserRole
from ..schemas import BookingCreate, BookingOut, ResourceOut

router = APIRouter(prefix="/api/resources", tags=["共享空间与预约"])

# 预约权限矩阵：学校侧（教师/校长）发起预约；社区/物业侧只审批不发起
_CAN_BOOK = {UserRole.teacher, UserRole.admin}
_CAN_APPROVE = {UserRole.community, UserRole.admin}


@router.get("", response_model=list[ResourceOut])
def list_resources(
    category: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(CommunityResource).filter(CommunityResource.available.is_(True))
    if category:
        q = q.filter(CommunityResource.category == category)
    if keyword:
        q = q.filter(CommunityResource.name.contains(keyword))
    return q.all()


@router.get("/parking")
def parking_status(db: Session = Depends(get_db)):
    """错峰停车实时空位：地磁传感器（占用数）→ 剩余车位。
    回应家长"周边停车位不够、早晚高峰拥堵"的真实评价：
    周边单位车位在接送高峰对家长开放，实时空位引导减少巡游绕圈。
    """
    lots = (
        db.query(CommunityResource)
        .filter(CommunityResource.category == "错峰停车",
                CommunityResource.available.is_(True))
        .all()
    )
    out = []
    for lot in lots:
        occupied = None
        if lot.parking_device_id:
            device = db.query(Device).filter(Device.device_id == lot.parking_device_id).first()
            if device:
                r = (
                    db.query(SensorReading)
                    .filter(SensorReading.device_pk == device.id)
                    .order_by(SensorReading.created_at.desc())
                    .first()
                )
                if r:
                    occupied = int(r.value)
        free = max(lot.capacity - occupied, 0) if occupied is not None else None
        out.append({
            "id": lot.id, "name": lot.name, "address": lot.address,
            "capacity": lot.capacity, "occupied": occupied, "free": free,
            "open_hours": lot.open_hours,
            "status": ("充足" if free is None or free >= lot.capacity * 0.3
                       else ("紧张" if free > 0 else "已满")),
        })
    return sorted(out, key=lambda x: -(x["free"] if x["free"] is not None else 0))


@router.get("/emergency-map")
def emergency_map(db: Session = Depends(get_db)):
    """平急两用视图：应急状态下各共享空间的角色与可容纳人数（本体 emergency_role 标注）"""
    rows = (
        db.query(CommunityResource)
        .filter(CommunityResource.emergency_role.isnot(None))
        .all()
    )
    return [
        {"id": r.id, "name": r.name, "address": r.address,
         "emergency_role": r.emergency_role, "capacity": r.capacity,
         "contact": r.contact}
        for r in rows
    ]


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    res = db.get(CommunityResource, resource_id)
    if not res:
        raise HTTPException(404, "资源不存在")
    return res


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return a_start < b_end and b_start < a_end


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db)):
    resource = db.get(CommunityResource, payload.resource_id)
    if not resource or not resource.available:
        raise HTTPException(404, "资源不存在或不可预约")
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.role not in _CAN_BOOK:
        raise HTTPException(403, "仅学校侧（教师/校长）可发起预约；社区侧负责审批")
    if payload.start_time >= payload.end_time:
        raise HTTPException(400, "结束时间必须晚于开始时间")
    if resource.capacity and payload.attendees > resource.capacity:
        raise HTTPException(400, f"人数超出场地容量（上限{resource.capacity}人）")

    # 冲突检测：同资源同日已确认/待确认预约的时段重叠
    existing = (
        db.query(Booking)
        .filter(
            Booking.resource_id == payload.resource_id,
            Booking.date == payload.date,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed]),
        )
        .all()
    )
    for b in existing:
        if _overlaps(payload.start_time, payload.end_time, b.start_time, b.end_time):
            raise HTTPException(
                409, f"时段冲突：{b.start_time}-{b.end_time} 已被预约（{b.booking_no}）"
            )

    today = datetime.now().strftime("%Y%m%d")
    count = db.query(Booking).filter(Booking.booking_no.like(f"BK-{today}-%")).count()
    booking = Booking(
        booking_no=f"BK-{today}-{count + 1:03d}",
        **payload.model_dump(),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/bookings/list", response_model=list[BookingOut])
def list_bookings(
    user_id: int | None = None,
    date: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Booking).order_by(Booking.date.desc())
    if user_id:
        q = q.filter(Booking.user_id == user_id)
    if date:
        q = q.filter(Booking.date == date)
    return q.limit(100).all()


@router.patch("/bookings/{booking_no}/status", response_model=BookingOut)
def update_booking(
    booking_no: str, status: BookingStatus,
    operator_id: int | None = None,
    db: Session = Depends(get_db),
):
    booking = db.query(Booking).filter(Booking.booking_no == booking_no).first()
    if not booking:
        raise HTTPException(404, "预约不存在")
    # 批准/驳回是社区侧（资源方）的职责；申请人只能取消自己的预约
    if operator_id is not None:
        op = db.get(User, operator_id)
        if not op:
            raise HTTPException(404, "操作人不存在")
        if status == BookingStatus.cancelled:
            if op.id != booking.user_id and op.role not in _CAN_APPROVE:
                raise HTTPException(403, "只能取消本人预约")
        elif op.role not in _CAN_APPROVE:
            raise HTTPException(403, "仅社区/管理侧可审批预约")
    booking.status = status
    db.commit()
    db.refresh(booking)
    return booking
