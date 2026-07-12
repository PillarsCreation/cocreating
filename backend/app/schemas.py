"""Pydantic 请求/响应模型（v4）"""
from datetime import datetime

from pydantic import BaseModel, Field

from .models import (
    BookingStatus,
    DeviceType,
    HazardStatus,
    IncidentCategory,
    IncidentStatus,
    NotifyLevel,
    UserRole,
)


# ---------- 用户 ----------

class UserCreate(BaseModel):
    name: str
    role: UserRole
    phone: str | None = None
    class_name: str | None = None


class UserOut(UserCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 工单 ----------

class IncidentCreate(BaseModel):
    reporter_id: int
    description: str = Field(min_length=2, max_length=500)
    location: str
    image_path: str | None = None


class IncidentUpdateStatus(BaseModel):
    to_status: IncidentStatus
    note: str | None = None
    operator: str = "admin"


class IncidentLogOut(BaseModel):
    from_status: str | None
    to_status: str
    note: str | None
    operator: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    id: int
    ticket_no: str
    reporter_id: int
    description: str
    image_path: str | None
    location: str
    category: IncidentCategory
    confidence: float
    status: IncidentStatus
    assignee: str | None
    priority: int
    source: str
    ref: str | None
    created_at: datetime
    resolved_at: datetime | None
    logs: list[IncidentLogOut] = []

    model_config = {"from_attributes": True}


class IncidentStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_source: dict[str, int]
    avg_resolve_hours: float | None


# ---------- 感知层 ----------

class DeviceOut(BaseModel):
    id: int
    device_id: str
    name: str
    dtype: DeviceType
    zone: str
    metric: str | None
    unit: str | None
    threshold_high: float | None
    threshold_low: float | None
    online: bool

    model_config = {"from_attributes": True}


class TelemetryIn(BaseModel):
    """MQTT 网关转发格式：topic redgate/{device_id}/{metric} → 本结构"""
    device_id: str
    metric: str
    value: float


class TelemetryOut(BaseModel):
    device_id: str
    metric: str
    value: float
    is_anomaly: bool
    threshold_high: float | None
    created_at: datetime


class VisionEventOut(BaseModel):
    id: int
    event_type: str
    confidence: float
    bbox: list | None
    snapshot_hash: str | None
    count: int
    zone: str
    device_id: str
    last_at: datetime


# ---------- 认知层：融合风险 ----------

class HazardOut(BaseModel):
    id: int
    hazard_class: str
    zone: str
    severity: int
    sources: list
    inference: str
    suggestion: str | None
    status: HazardStatus
    created_at: datetime
    cleared_at: datetime | None

    model_config = {"from_attributes": True}


# ---------- 决策层：预案 ----------

class AlertIn(BaseModel):
    """官方预警接入（气象/地震预警接口的标准化落地格式）"""
    alert_type: str = Field(pattern=r"^[a-z_]+$")   # rainstorm/typhoon/earthquake/heat/air_pollution/wind
    alert_level: str = Field(pattern=r"^[a-z]+$")   # blue/yellow/orange/red/warning
    operator: str = "official-feed"
    source: str = "official"


class PlanOut(BaseModel):
    id: int
    alert_type: str
    alert_level: str
    mode: str
    actions: list
    operator: str
    source: str
    active: bool
    created_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


# ---------- 处置层：通知 ----------

class NotificationCreate(BaseModel):
    title: str = Field(max_length=120)
    body: str
    level: NotifyLevel = NotifyLevel.info
    audience_roles: list[str]
    audience_class: str | None = None
    created_by: str = "admin"


class NotificationOut(BaseModel):
    id: int
    title: str
    body: str
    level: NotifyLevel
    audience_roles: list
    audience_class: str | None
    hazard_id: int | None
    plan_id: int | None
    created_by: str
    created_at: datetime
    read_at: datetime | None = None   # 当前用户视角

    model_config = {"from_attributes": True}


class ReceiptStats(BaseModel):
    notification_id: int
    total: int
    read: int
    unread: int
    escalated: list[dict]   # 未读升级补呼清单 [{user_id,name,phone}]


# ---------- 处置层：资产 ----------

class AssetOut(BaseModel):
    id: int
    code: str
    name: str
    category: str
    location: str
    grade: int | None
    class_name: str | None
    quantity: int
    purchased_year: int | None
    condition: int
    air_device_id: str | None

    model_config = {"from_attributes": True}


class AssetReportIn(BaseModel):
    """扫码报修：资产码 + 问题描述 → 自动生成 facility 工单"""
    reporter_id: int
    description: str = Field(min_length=2, max_length=300)


# ---------- 处置层：食安 ----------

class CanteenSampleCreate(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    meal: str
    dish: str
    weight_g: int = 125
    fridge_device_id: str
    operator: str


class CanteenSampleOut(CanteenSampleCreate):
    id: int
    disposed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 资源与预约 ----------

class ResourceOut(BaseModel):
    id: int
    name: str
    category: str
    address: str
    capacity: int
    contact: str | None
    tags: list | None
    open_hours: dict | None
    emergency_role: str | None
    parking_device_id: str | None
    available: bool
    description: str | None

    model_config = {"from_attributes": True}


class BookingCreate(BaseModel):
    resource_id: int
    user_id: int
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    purpose: str
    attendees: int = 0


class BookingOut(BaseModel):
    id: int
    booking_no: str
    resource_id: int
    user_id: int
    date: str
    start_time: str
    end_time: str
    purpose: str
    attendees: int
    status: BookingStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 潮汐安全 ----------

class SafetySlotOut(BaseModel):
    weekday: int
    hour: int
    zone: str
    crowd_index: float
    traffic_index: float
    incident_count: int
    risk_score: float

    model_config = {"from_attributes": True}


class PickupScheduleOut(BaseModel):
    class_name: str
    weekday: int
    dismiss_time: str
    gate: str
    note: str | None

    model_config = {"from_attributes": True}


class SafetyAlert(BaseModel):
    zone: str
    weekday: int
    hour: int
    risk_score: float
    level: str
    suggestion: str


# ---------- AI 对话 ----------

class ChatRequest(BaseModel):
    role: UserRole
    message: str


class ChatResponse(BaseModel):
    intent: str
    reply: str
    data: dict | list | None = None


# ==================== v4：健康成长 / 学习服务 / 家校效能 ====================

# ---------- 学生档案（一人一档、不一人一号） ----------

class StudentOut(BaseModel):
    id: int
    name: str
    class_name: str
    grade: int
    gender: str
    birth_year: int | None
    parent_id: int
    interests: list | None

    model_config = {"from_attributes": True}


class InterestsIn(BaseModel):
    """孩子兴趣意愿标签（家长代填）"""
    interests: list[str] = Field(max_length=10)


# ---------- 健康档案 ----------

class HealthRecordOut(BaseModel):
    id: int
    term: str
    height_cm: float
    weight_kg: float
    vision_left: float | None
    vision_right: float | None
    dental_caries: int

    model_config = {"from_attributes": True}


class FitnessRecordOut(BaseModel):
    id: int
    term: str
    item: str
    value: float
    unit: str
    score: int
    source: str

    model_config = {"from_attributes": True}


class AcademicRecordOut(BaseModel):
    term: str
    subject: str
    level: str

    model_config = {"from_attributes": True}


class ExternalClassIn(BaseModel):
    category: str = Field(pattern=r"^(体育|艺术|科技|人文|劳动)$")
    name: str = Field(min_length=1, max_length=60)
    weekly_hours: float = Field(default=1, ge=0.5, le=20)


class ExternalClassOut(ExternalClassIn):
    id: int
    student_id: int

    model_config = {"from_attributes": True}


class FitnessVideoIn(BaseModel):
    """AI 体测：大课间/家庭录制动作视频 → 骨架关键点计数（只存关键点结果，不存视频）"""
    item: str = Field(pattern=r"^(一分钟跳绳|仰卧起坐|开合跳)$")
    term: str = Field(max_length=20)


# ---------- 选修课与推荐 ----------

class CourseOut(BaseModel):
    id: int
    name: str
    category: str
    teacher: str
    weekday: int
    time_slot: str
    capacity: int
    enrolled: int
    intro: str | None

    model_config = {"from_attributes": True}


class RecommendedCourse(CourseOut):
    """个性化推荐结果：每条带可解释理由；excluded=已在校外学同类"""
    match_score: int = 0
    reasons: list[str] = []
    tag: str | None = None       # 优先推荐 / 探索推荐 / None
    excluded: bool = False
    conflict: str | None = None  # 时段冲突/名额已满提示


class EnrollIn(BaseModel):
    student_id: int
    operator_parent_id: int      # 监护人操作（学生无账号）
    reason: str | None = None    # 推荐理由快照（可解释留痕）


# ---------- 请假台账 ----------

class LeaveCreate(BaseModel):
    student_id: int
    parent_id: int               # 发起人须为该生监护人
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    leave_type: str = Field(pattern=r"^(sick|personal)$")
    symptoms: list[str] | None = None   # 病假症状标签（发热/咳嗽/呕吐/腹泻/皮疹…）
    note: str | None = Field(default=None, max_length=200)


class LeaveOut(BaseModel):
    id: int
    student_id: int
    start_date: str
    end_date: str
    days: float
    leave_type: str
    symptoms: list | None
    note: str | None
    status: str
    approved_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaveApprove(BaseModel):
    operator_id: int             # 班主任/校长
    approve: bool
    comment: str | None = None


# ---------- 用餐日历（无余额·银行卡后付费） ----------

class MealPlanUpsert(BaseModel):
    student_id: int
    parent_id: int
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    days: list[int] = Field(max_length=31)


class MealPlanOut(BaseModel):
    id: int
    student_id: int
    month: str
    days: list
    price_per_meal: float
    billed: bool

    model_config = {"from_attributes": True}


# ---------- 年检公示 ----------

class InspectionOut(BaseModel):
    id: int
    target: str
    category: str
    item: str
    result: str
    report_no: str | None
    inspect_date: str
    next_due: str | None
    passed: bool

    model_config = {"from_attributes": True}


# ---------- 场馆点评 ----------

class ReviewCreate(BaseModel):
    resource_id: int
    teacher_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=2, max_length=500)
    visit_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ReviewOut(BaseModel):
    id: int
    resource_id: int
    teacher_name: str
    rating: int
    comment: str
    visit_date: str

    model_config = {"from_attributes": True}
