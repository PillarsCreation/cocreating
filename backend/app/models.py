"""红门哨兵 · 数据模型层（v4 平急结合校园安全与成长智能体）

急时（安全防范）四层架构数据域：
- 感知层：Device（IoT设备/边缘相机注册表）、SensorReading（遥测）、VisionEvent（边缘AI结构化事件）
- 认知层：HazardEvent（多模态信号交叉印证后的融合风险事件）
- 决策层：PlanActivation（预警→校园运行模式切换的审计记录）
- 处置层：Incident 工单、Notification 分级分众通知（回执可追）、Asset 固定资产台账、
          CanteenSample 食堂留样、CommunityResource 平急两用共享空间/错峰车位

平时（教联体数字底座）数据域（v4新增）：
- Student 学生档案（一人一档不一人一号，挂家长账号）
- HealthRecord/FitnessRecord/AcademicRecord 健康·体测·成绩纵向档案
- Course/CourseEnrollment/ExternalClass 选修课AI推荐与校外班排除
- LeaveRequest 请假台账（症状标签→缺勤聚集预警）、MealPlan 用餐日历（后付费无余额）
- AssetInspection 年检公示墙、VenueReview 场馆点评
"""
import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ---------- 枚举 ----------

class UserRole(str, enum.Enum):
    """4角色账号体系。学生一人一档、不一人一号（见 Student 模型），不设登录角色。"""
    teacher = "teacher"
    parent = "parent"
    community = "community"
    admin = "admin"


class IncidentCategory(str, enum.Enum):
    """工单分类：校门口治理 + 校内食安/空气/资产"""
    traffic = "traffic"            # 校门口拥堵/违停
    vendor = "vendor"              # 游商占道
    fire_hazard = "fire_hazard"    # 电动车/消防隐患
    environment = "environment"    # 垃圾/环境卫生/噪音
    facility = "facility"          # 设施损坏（含桌椅资产报修）
    food = "food"                  # 食堂食品安全（异物/变质/冷链）
    air = "air"                    # 室内空气（甲醛/TVOC/异味）
    flood = "flood"                # 积水内涝
    other = "other"


class IncidentStatus(str, enum.Enum):
    reported = "reported"
    dispatched = "dispatched"
    processing = "processing"
    resolved = "resolved"
    closed = "closed"


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class DeviceType(str, enum.Enum):
    camera = "camera"          # 边缘AI相机（只回传结构化事件，原始视频不出端）
    water = "water"            # 积水水位计
    noise = "noise"            # 噪音计
    weather = "weather"        # 微气象站（雨量/风速）
    fridge = "fridge"          # 食堂留样柜/冷柜温度
    air = "air"                # 教室甲醛/CO2/TVOC
    parking = "parking"        # 地磁车位检测


class HazardStatus(str, enum.Enum):
    active = "active"          # 已确认，待处置
    mitigating = "mitigating"  # 处置中
    cleared = "cleared"        # 已解除


class NotifyLevel(str, enum.Enum):
    info = "info"              # 普通：应用内
    important = "important"    # 重要：应用内+需回执
    emergency = "emergency"    # 紧急：需回执+超时升级（短信/电话补呼清单）


# ---------- 用户 ----------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    class_name: Mapped[str | None] = mapped_column(String(20), default=None)  # 学生/家长关联班级
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incidents: Mapped[list["Incident"]] = relationship(back_populates="reporter")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


# ---------- 感知层 ----------

class Device(Base):
    """IoT设备/边缘节点注册表。接入协议：MQTT 网关转 HTTP 上报（topic 映射 device_id/metric）"""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # 如 iot-water-eastgate-01
    name: Mapped[str] = mapped_column(String(80))
    dtype: Mapped[DeviceType] = mapped_column(Enum(DeviceType), index=True)
    zone: Mapped[str] = mapped_column(String(50), index=True)      # 部署区域（与本体 Zone 对齐）
    metric: Mapped[str | None] = mapped_column(String(30), default=None)   # water_level_cm / hcho_mg ...
    unit: Mapped[str | None] = mapped_column(String(15), default=None)
    threshold_high: Mapped[float | None] = mapped_column(Float, default=None)  # 越限即异常
    threshold_low: Mapped[float | None] = mapped_column(Float, default=None)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict | None] = mapped_column(JSON, default=None)

    readings: Mapped[list["SensorReading"]] = relationship(back_populates="device")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_pk: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    metric: Mapped[str] = mapped_column(String(30), index=True)
    value: Mapped[float] = mapped_column(Float)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    device: Mapped["Device"] = relationship(back_populates="readings")


class VisionEvent(Base):
    """边缘AI相机回传的结构化事件。
    数据安全设计：原始帧在边缘节点推理后即丢弃，云端只存事件类型/框坐标/快照哈希——不含人脸与可识别画面。
    """
    __tablename__ = "vision_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_pk: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)  # illegal_parking / waterlogging / kitchen_no_hat ...
    confidence: Mapped[float] = mapped_column(Float)
    bbox: Mapped[list | None] = mapped_column(JSON, default=None)    # [x,y,w,h] 归一化
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), default=None)  # SHA-256，取证但不留原图
    count: Mapped[int] = mapped_column(Integer, default=1)           # 冷却窗口内去重累计
    first_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# ---------- 认知层：融合风险事件 ----------

class HazardEvent(Base):
    """本体推理产出：多模态信号（传感器/视频/群众上报/官方预警）交叉印证后的确认风险"""
    __tablename__ = "hazard_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    hazard_class: Mapped[str] = mapped_column(String(40), index=True)  # waterlogging / food_safety / air_quality ...
    zone: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[int] = mapped_column(Integer, default=2)          # 1提示 2一般 3严重 4紧急
    sources: Mapped[list] = mapped_column(JSON)                        # [{"type":"sensor","ref":"iot-..","detail":..}]
    inference: Mapped[str] = mapped_column(Text)                       # 推理链文本（可解释性）
    suggestion: Mapped[str | None] = mapped_column(Text, default=None) # 本体查询出的处置建议+责任方
    status: Mapped[HazardStatus] = mapped_column(Enum(HazardStatus), default=HazardStatus.active, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


# ---------- 决策层：预案引擎 ----------

class PlanActivation(Base):
    """官方预警 → 校园运行模式切换记录（每次切换留审计痕）"""
    __tablename__ = "plan_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(30))    # rainstorm / typhoon / earthquake / heat / air_pollution
    alert_level: Mapped[str] = mapped_column(String(15))   # blue / yellow / orange / red / warning
    mode: Mapped[str] = mapped_column(String(30))          # normal / staggered / indoor / home_study / evacuate
    actions: Mapped[list] = mapped_column(JSON)            # 预案动作清单（含已自动执行标记）
    operator: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(20), default="official")  # official / manual / scenario
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


# ---------- 处置层：工单 ----------

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(255), default=None)
    location: Mapped[str] = mapped_column(String(120))
    category: Mapped[IncidentCategory] = mapped_column(
        Enum(IncidentCategory), default=IncidentCategory.other, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), default=IncidentStatus.reported, index=True
    )
    assignee: Mapped[str | None] = mapped_column(String(50), default=None)
    priority: Mapped[int] = mapped_column(Integer, default=2)   # 1紧急 2普通 3低
    source: Mapped[str] = mapped_column(String(20), default="citizen", index=True)  # citizen/vision/iot/asset/scenario
    ref: Mapped[str | None] = mapped_column(String(60), default=None)  # 关联感知事件/资产编码
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    reporter: Mapped["User"] = relationship(back_populates="incidents")
    logs: Mapped[list["IncidentLog"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentLog(Base):
    __tablename__ = "incident_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"))
    from_status: Mapped[str | None] = mapped_column(String(20), default=None)
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, default=None)
    operator: Mapped[str] = mapped_column(String(50), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incident: Mapped["Incident"] = relationship(back_populates="logs")


# ---------- 处置层：分级分众通知（对标并超越微信群） ----------

class Notification(Base):
    """相比微信群的四个不可替代点：定向到人、回执可查、未读升级、紧急穿透（免打扰置顶）"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    level: Mapped[NotifyLevel] = mapped_column(Enum(NotifyLevel), default=NotifyLevel.info, index=True)
    audience_roles: Mapped[list] = mapped_column(JSON)                 # ["parent","teacher"]
    audience_class: Mapped[str | None] = mapped_column(String(20), default=None)  # 限定班级
    hazard_id: Mapped[int | None] = mapped_column(ForeignKey("hazard_events.id"), default=None)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plan_activations.id"), default=None)
    created_by: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    receipts: Mapped[list["NotificationReceipt"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )


class NotificationReceipt(Base):
    __tablename__ = "notification_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)   # 紧急通知超时未读→列入电话补呼清单

    notification: Mapped["Notification"] = relationship(back_populates="receipts")


# ---------- 处置层：固定资产台账（桌椅/翻新工程） ----------

class Asset(Base):
    """资产二维码台账：扫码报修联动工单；翻新工程资产联动教室空气传感器做甲醛公示"""
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)   # AS-G6C1-DESK
    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(30), index=True)  # desk/chair/multimedia/renovation/sports
    location: Mapped[str] = mapped_column(String(60))
    grade: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    class_name: Mapped[str | None] = mapped_column(String(20), default=None)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    purchased_year: Mapped[int | None] = mapped_column(Integer, default=None)
    condition: Mapped[int] = mapped_column(Integer, default=5)     # 1报废~5全新
    air_device_id: Mapped[str | None] = mapped_column(String(40), default=None)  # 翻新工程关联的空气传感器
    meta: Mapped[dict | None] = mapped_column(JSON, default=None)


# ---------- 处置层：食堂食安闭环 ----------

class CanteenSample(Base):
    """留样台账：每餐每菜 125g 冷藏 48h（GB 31654），与留样柜温度传感器联动"""
    __tablename__ = "canteen_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String(10), index=True)      # "2026-07-21"
    meal: Mapped[str] = mapped_column(String(10))                  # breakfast / lunch
    dish: Mapped[str] = mapped_column(String(60))
    weight_g: Mapped[int] = mapped_column(Integer, default=125)
    fridge_device_id: Mapped[str] = mapped_column(String(40))      # 关联留样柜温度设备
    operator: Mapped[str] = mapped_column(String(50))
    disposed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------- 平急两用共享空间 / 错峰车位 ----------

class CommunityResource(Base):
    """周边单位空间目录：平时供教学/家长错峰停车，急时按本体标注转为应急避难/物资点"""
    __tablename__ = "community_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(30), index=True)  # 共享空间/错峰停车/实践基地
    address: Mapped[str] = mapped_column(String(150))
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    contact: Mapped[str | None] = mapped_column(String(50), default=None)
    tags: Mapped[list | None] = mapped_column(JSON, default=None)
    open_hours: Mapped[dict | None] = mapped_column(JSON, default=None)
    emergency_role: Mapped[str | None] = mapped_column(String(40), default=None)  # 避难点/物资点/临时医疗点
    parking_device_id: Mapped[str | None] = mapped_column(String(40), default=None)  # 地磁传感器→实时空位
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="resource")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("community_resources.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[str] = mapped_column(String(10), index=True)
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    purpose: Mapped[str] = mapped_column(String(200))
    attendees: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    resource: Mapped["CommunityResource"] = relationship(back_populates="bookings")
    user: Mapped["User"] = relationship(back_populates="bookings")


# ---------- 潮汐安全（保留：错峰接送画像） ----------

class SafetySlot(Base):
    __tablename__ = "safety_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, index=True)
    hour: Mapped[int] = mapped_column(Integer, index=True)
    zone: Mapped[str] = mapped_column(String(50))
    crowd_index: Mapped[float] = mapped_column(Float, default=0)
    traffic_index: Mapped[float] = mapped_column(Float, default=0)
    incident_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0)


class PickupSchedule(Base):
    __tablename__ = "pickup_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_name: Mapped[str] = mapped_column(String(20), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    dismiss_time: Mapped[str] = mapped_column(String(5))
    gate: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(120), default=None)


# ==================== v4：健康成长 / 学习服务 / 家校效能 ====================

class Student(Base):
    """学生档案：一人一档、不一人一号。
    学生不设登录账号（1-3年级无自主使用能力、无手机、数据最小化合规），
    档案挂在家长账号下，家长是唯一监护登录主体。
    """
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    class_name: Mapped[str] = mapped_column(String(20), index=True)
    grade: Mapped[int] = mapped_column(Integer, index=True)          # 1-6（本校仅六个年级）
    gender: Mapped[str] = mapped_column(String(2), default="男")
    birth_year: Mapped[int | None] = mapped_column(Integer, default=None)
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    interests: Mapped[list | None] = mapped_column(JSON, default=None)  # 孩子兴趣意愿标签（家长代填）


class HealthRecord(Base):
    """每学期体检档案：身高/体重/视力/口腔，纵向对比生成生长曲线与营养建议"""
    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    term: Mapped[str] = mapped_column(String(20), index=True)        # "2025-2026上"
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    vision_left: Mapped[float | None] = mapped_column(Float, default=None)   # 5.0记录法
    vision_right: Mapped[float | None] = mapped_column(Float, default=None)
    dental_caries: Mapped[int] = mapped_column(Integer, default=0)   # 龋齿数
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FitnessRecord(Base):
    """体测成绩：国标项目 + AI视频计数来源标注（骨架关键点，不存原始视频）"""
    __tablename__ = "fitness_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    term: Mapped[str] = mapped_column(String(20), index=True)
    item: Mapped[str] = mapped_column(String(30))                    # 一分钟跳绳/50米跑/坐位体前屈/肺活量
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)           # 国标折算分 0-100
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual / ai_video
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcademicRecord(Base):
    """成绩等级：只做个人纵向对比（优/良/中/待提高），不做班级排名公示（教育部红线）"""
    __tablename__ = "academic_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    term: Mapped[str] = mapped_column(String(20), index=True)
    subject: Mapped[str] = mapped_column(String(20))
    level: Mapped[str] = mapped_column(String(10))                   # 优/良/中/待提高


class ExternalClass(Base):
    """校外兴趣班登记：已在外学的类别，选修课推荐自动排除，避免重复报班"""
    __tablename__ = "external_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))                # 体育/艺术/科技/人文/劳动
    name: Mapped[str] = mapped_column(String(60))
    weekly_hours: Mapped[float] = mapped_column(Float, default=1)


class Course(Base):
    """校内选修课/课后服务课程"""
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(20), index=True)    # 体育/艺术/科技/人文/劳动
    teacher: Mapped[str] = mapped_column(String(50))
    weekday: Mapped[int] = mapped_column(Integer)                    # 0-4
    time_slot: Mapped[str] = mapped_column(String(20))               # "15:30-16:30"
    capacity: Mapped[int] = mapped_column(Integer, default=30)
    enrolled: Mapped[int] = mapped_column(Integer, default=0)
    intro: Mapped[str | None] = mapped_column(Text, default=None)


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String(15), default="enrolled")  # enrolled / cancelled
    reason: Mapped[str | None] = mapped_column(Text, default=None)   # 报名时的推荐理由快照（可解释留痕）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LeaveRequest(Base):
    """请假台账：家长发起→班主任批准→自动落账。
    班级维度可统计每生每月/学期请假天数；病假症状标签供缺勤聚集预警（因病缺课追踪是国家强制要求）。
    """
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    start_date: Mapped[str] = mapped_column(String(10), index=True)
    end_date: Mapped[str] = mapped_column(String(10))
    days: Mapped[float] = mapped_column(Float, default=1)
    leave_type: Mapped[str] = mapped_column(String(10), index=True)  # sick / personal
    symptoms: Mapped[list | None] = mapped_column(JSON, default=None)  # ["发热","咳嗽"]
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending/approved/rejected
    approved_by: Mapped[str | None] = mapped_column(String(50), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class MealPlan(Base):
    """用餐日历：替代微信群接龙。家长按月勾选用餐日，月末按实际天数生成账单，
    银行卡后付费——无饭卡、无余额概念。食堂按次日各班人数备餐。
    """
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)        # "2026-09"
    days: Mapped[list] = mapped_column(JSON, default=list)           # [1,2,3,...] 勾选的用餐日
    price_per_meal: Mapped[float] = mapped_column(Float, default=14)
    billed: Mapped[bool] = mapped_column(Boolean, default=False)     # 月末生成账单后置真
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssetInspection(Base):
    """年检公示墙：装修检化验/直饮水/消防器材/教室照明/体育器械/急救箱。
    效期与超期由规则引擎自动判定并提醒。
    """
    __tablename__ = "asset_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(80))                  # 检查对象
    category: Mapped[str] = mapped_column(String(30), index=True)    # renovation/water/fire/lighting/sports/medkit
    item: Mapped[str] = mapped_column(String(80))                    # 检查项（甲醛检化验/滤芯更换/压力效期…）
    result: Mapped[str] = mapped_column(String(120))
    report_no: Mapped[str | None] = mapped_column(String(40), default=None)  # 检化验报告编号
    inspect_date: Mapped[str] = mapped_column(String(10))
    next_due: Mapped[str | None] = mapped_column(String(10), default=None)   # 下次到期日
    passed: Mapped[bool] = mapped_column(Boolean, default=True)


class VenueReview(Base):
    """场馆点评：教师带队参观后评价，后续教师订场地先看口碑，差评规避"""
    __tablename__ = "venue_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("community_resources.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    teacher_name: Mapped[str] = mapped_column(String(50))
    rating: Mapped[int] = mapped_column(Integer)                     # 1-5
    comment: Mapped[str] = mapped_column(Text)
    visit_date: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
