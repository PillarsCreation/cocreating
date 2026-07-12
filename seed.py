"""种子数据（v4）：大兴区西红门实验二小 · 红门哨兵演示底座

急时线：IoT设备/边缘相机注册表、固定资产台账、食堂留样、共享空间、安全画像、接送错峰表
平时线（教联体）：六年级1班学生档案（一人一档挂家长账号）、多学期健康/体测/成绩、
选修课目录、校外兴趣班、请假台账、用餐日历、年检公示7门类、场馆点评、家庭安全提示

运行：python seed.py（幂等：已有用户则跳过；重建请先 drop_all）
"""
import calendar
from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.models import (
    AcademicRecord,
    Asset,
    AssetInspection,
    Booking,
    BookingStatus,
    CanteenSample,
    CommunityResource,
    Course,
    CourseEnrollment,
    Device,
    DeviceType,
    ExternalClass,
    FitnessRecord,
    HealthRecord,
    LeaveRequest,
    MealPlan,
    Notification,
    NotificationReceipt,
    NotifyLevel,
    PickupSchedule,
    SafetySlot,
    Student,
    User,
    UserRole,
    VenueReview,
)

Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("已有数据，跳过种子写入（如需重建请先 drop_all）")
            return

        today = datetime.now().date()

        # ---------- 用户（4角色；学生一人一档不一人一号，无学生账号） ----------
        teacher = User(name="李老师", role=UserRole.teacher, class_name="六年级1班", phone="13800000001")
        parent = User(name="王女士", role=UserRole.parent, class_name="六年级1班", phone="13800000002")
        community = User(name="张主任", role=UserRole.community, phone="13800000003")
        admin = User(name="赵校长", role=UserRole.admin, phone="13800000004")
        db.add_all([teacher, parent, community, admin])
        db.flush()

        # ---------- 感知层：IoT设备与边缘相机注册表（metric 与本体规则 key 对齐） ----------
        devices = [
            Device(device_id="iot-water-eastgate-01", name="东门下凹路段水位计",
                   dtype=DeviceType.water, zone="东门下凹路段",
                   metric="water_level_cm", unit="cm", threshold_high=15),
            Device(device_id="iot-weather-roof-01", name="屋面微气象站（雨量/风速）",
                   dtype=DeviceType.weather, zone="全校",
                   metric="wind_ms", unit="m/s", threshold_high=13.9),
            Device(device_id="iot-air-class601-01", name="六年级1班甲醛监测（暑期翻新重点盯防）",
                   dtype=DeviceType.air, zone="翻新教室(六年级1班)",
                   metric="hcho_mg", unit="mg/m³", threshold_high=0.08),
            Device(device_id="iot-tvoc-class601-01", name="六年级1班TVOC监测",
                   dtype=DeviceType.air, zone="翻新教室(六年级1班)",
                   metric="tvoc_mg", unit="mg/m³", threshold_high=0.60),
            Device(device_id="iot-fridge-canteen-01", name="食堂留样柜温度（GB 31654 冷藏0-8℃）",
                   dtype=DeviceType.fridge, zone="食堂留样间",
                   metric="fridge_temp_c", unit="℃", threshold_high=8),
            Device(device_id="iot-noise-eastgate-01", name="东门噪音计（接送高峰声学监测）",
                   dtype=DeviceType.noise, zone="东门",
                   metric="noise_db", unit="dB", threshold_high=70),
            Device(device_id="iot-noise-stair-01", name="楼梯间噪音计（下课峰值，与视觉密度交叉印证）",
                   dtype=DeviceType.noise, zone="六年级教学楼·楼梯间",
                   metric="stair_noise_db", unit="dB", threshold_high=75),
            Device(device_id="iot-parking-tower-01", name="商务楼宇车位地磁",
                   dtype=DeviceType.parking, zone="京开辅路口",
                   metric="occupied", unit="辆"),
            Device(device_id="iot-parking-plaza-01", name="理想城商业广场车位地磁",
                   dtype=DeviceType.parking, zone="理想城",
                   metric="occupied", unit="辆"),
            Device(device_id="cam-eastgate-01", name="东门边缘AI相机（积水/违停/人群密度）",
                   dtype=DeviceType.camera, zone="东门"),
            Device(device_id="cam-southgate-01", name="南门边缘AI相机（消防通道/游商）",
                   dtype=DeviceType.camera, zone="南门"),
            Device(device_id="cam-kitchen-01", name="明厨亮灶边缘AI（厨帽/口罩/鼠患）",
                   dtype=DeviceType.camera, zone="食堂后厨"),
            Device(device_id="cam-stair-g6-01", name="楼梯间边缘AI相机（只出密度值不出人脸）",
                   dtype=DeviceType.camera, zone="六年级教学楼·楼梯间"),
        ]
        db.add_all(devices)
        db.flush()
        # 初始地磁读数（错峰车位实时空位演示）
        from app.models import SensorReading
        dev_by_id = {d.device_id: d for d in devices}
        db.add(SensorReading(device_pk=dev_by_id["iot-parking-tower-01"].id,
                             metric="occupied", value=41, is_anomaly=False))
        db.add(SensorReading(device_pk=dev_by_id["iot-parking-plaza-01"].id,
                             metric="occupied", value=62, is_anomaly=False))

        # ---------- 固定资产台账（admin专属；六年级1班精确到班） ----------
        assets = [
            Asset(code="AS-G6C1-DESK", name="课桌椅（六年级1班）", category="desk",
                  location="六年级1班", grade=6, class_name="六年级1班",
                  quantity=45, purchased_year=2017, condition=2,
                  meta={"note": "2017年购置成色差；现配3号桌，与体检身高匹配率联动年检公示"}),
            Asset(code="AS-G6-DESK", name="课桌椅（六年级2-6班）", category="desk",
                  location="六年级教学楼", grade=6, quantity=135,
                  purchased_year=2019, condition=3),
            Asset(code="AS-G1G5-DESK", name="课桌椅（1-5年级）", category="desk",
                  location="低中年级教学楼", quantity=900, purchased_year=2021, condition=4),
            Asset(code="AS-SPORT-RACK", name="室外单双杠", category="sports",
                  location="操场", quantity=6, purchased_year=2016, condition=2,
                  meta={"note": "超龄+螺栓锈蚀，年检不合格已停用待检修"}),
            Asset(code="AS-RENO-601", name="暑期翻新工程（六年级1班）", category="renovation",
                  location="翻新教室(六年级1班)", grade=6, class_name="六年级1班",
                  quantity=1, purchased_year=2025, condition=5,
                  air_device_id="iot-air-class601-01",
                  meta={"note": "2025年8月完工，在线监测+第三方检化验双保险"}),
        ]
        db.add_all(assets)

        # ---------- 食堂留样（近3日午餐各3道菜） ----------
        for i in range(3):
            d = (today - timedelta(days=i)).isoformat()
            for dish in ("西红柿炒鸡蛋", "土豆炖牛肉", "二米饭"):
                db.add(CanteenSample(date=d, meal="lunch", dish=dish, weight_g=125,
                                     fridge_device_id="iot-fridge-canteen-01",
                                     operator="食堂·刘师傅"))

        # ---------- 平急两用共享空间 ----------
        resources = [
            CommunityResource(name="街道文体中心·篮球馆", category="共享空间",
                              address="西红门镇兴华大街12号（距校650米）", capacity=200,
                              contact="6021-0001", emergency_role="应急避难点",
                              open_hours={"平日": "放学后", "周末": "全天"},
                              tags=["体育", "馆校合作"]),
            CommunityResource(name="理想城社区·多功能活动室", category="共享空间",
                              address="理想城小区北门（距校400米）", capacity=80,
                              contact="6021-0002", emergency_role="临时集散点",
                              open_hours={"全周": "预约开放"}, tags=["活动"]),
            CommunityResource(name="社区卫生服务中心·健康小屋", category="实践基地",
                              address="欣荣大街9号（距校500米）", capacity=30,
                              contact="6021-0003", emergency_role="应急医疗点",
                              open_hours={"工作日": "8:00-17:00"}, tags=["医教互促"]),
            CommunityResource(name="区图书馆·少儿分馆", category="实践基地",
                              address="兴丰大街38号（距校1.2公里）", capacity=120,
                              contact="6021-0004", emergency_role="备用安置点",
                              open_hours={"周二至周日": "9:00-17:00"}, tags=["研学", "社教同频"]),
            CommunityResource(name="消防救援站·科普教室", category="实践基地",
                              address="西红门消防站（距校900米）", capacity=40,
                              contact="6021-0005", emergency_role="消防联动点",
                              open_hours={"全周": "预约开放"}, tags=["安全教育"]),
            CommunityResource(name="商务楼宇·错峰共享车位", category="错峰停车",
                              address="京开辅路口写字楼B1（距校300米）", capacity=60,
                              contact="6021-0006", emergency_role="应急车辆集结区",
                              open_hours={"早高峰": "7:00-9:00", "晚高峰": "16:00-18:00"},
                              parking_device_id="iot-parking-tower-01", tags=["家校互动"]),
            CommunityResource(name="理想城商业广场·错峰车位", category="错峰停车",
                              address="理想城商业广场P2（距校450米）", capacity=80,
                              contact="6021-0008",
                              open_hours={"早高峰": "7:00-9:00", "晚高峰": "15:00-18:00"},
                              parking_device_id="iot-parking-plaza-01", tags=["家校互动"]),
            CommunityResource(name="科技园·青少年创客空间", category="实践基地",
                              address="西红门科技园3号楼（距校1.5公里）", capacity=50,
                              contact="6021-0007",
                              open_hours={"周末": "9:00-16:00"}, tags=["科技", "研学"]),
            CommunityResource(name="人防工程·地下活动空间", category="共享空间",
                              address="欣旺大街地下人防（距校800米）", capacity=300,
                              contact="6021-0009", emergency_role="人防掩蔽所",
                              open_hours={"全周": "预约开放"}, tags=["平急两用"]),
        ]
        db.add_all(resources)
        db.flush()

        # 一条已确认预约（教师发起、社区已批准）
        db.add(Booking(booking_no="BK-DEMO-001", resource_id=resources[0].id,
                       user_id=teacher.id, date=(today + timedelta(days=3)).isoformat(),
                       start_time="15:40", end_time="17:00",
                       purpose="六年级1班篮球选修课外训（馆校合作）", attendees=24,
                       status=BookingStatus.confirmed))

        # ---------- 场馆点评（教师参观后口碑；差评供后续规避） ----------
        db.add_all([
            VenueReview(resource_id=resources[0].id, teacher_id=teacher.id,
                        teacher_name="李老师", rating=5,
                        comment="场地宽敞、地胶新、有独立饮水区，带班体验很好，管理员配合疏导。",
                        visit_date=(today - timedelta(days=30)).isoformat()),
            VenueReview(resource_id=resources[3].id, teacher_id=teacher.id,
                        teacher_name="李老师", rating=4,
                        comment="少儿区藏书丰富，建议提前预约集体阅览室，散客时段较吵。",
                        visit_date=(today - timedelta(days=45)).isoformat()),
            VenueReview(resource_id=resources[7].id, teacher_id=admin.id,
                        teacher_name="赵校长", rating=2,
                        comment="设备老旧且当天无讲解员，40人只有1名工作人员接待，安全看护压力大，不建议整班前往。",
                        visit_date=(today - timedelta(days=60)).isoformat()),
        ])

        # ---------- 通学安全画像（周一至周五 × 早/午/晚高峰，东门为热点） ----------
        for wd in range(5):
            db.add_all([
                SafetySlot(weekday=wd, hour=7, zone="东门", crowd_index=0.8,
                           traffic_index=0.85, incident_count=2, risk_score=4.1),
                SafetySlot(weekday=wd, hour=12, zone="东门", crowd_index=0.35,
                           traffic_index=0.3, incident_count=0, risk_score=1.6),
                SafetySlot(weekday=wd, hour=15, zone="东门", crowd_index=0.95,
                           traffic_index=0.9, incident_count=3, risk_score=4.8),
                SafetySlot(weekday=wd, hour=16, zone="东门", crowd_index=0.55,
                           traffic_index=0.5, incident_count=1, risk_score=2.7),
                SafetySlot(weekday=wd, hour=15, zone="南门", crowd_index=0.4,
                           traffic_index=0.35, incident_count=0, risk_score=1.9),
            ])
        db.add_all([
            PickupSchedule(class_name="六年级1班", weekday=w, dismiss_time="15:40",
                           gate="东门", note="课后服务日16:40离校")
            for w in range(5)
        ])

        # ---------- 学生档案：一人一档挂家长账号（六年级1班演示班） ----------
        # 小明是主线人物（王女士之子）；其余同学各挂自己的家长（不开演示登录入口），
        # 保证"仅本家长可见孩子档案"的隐私边界真实成立
        other_parents = [
            User(name=f"六1家长{i}", role=UserRole.parent, class_name="六年级1班",
                 phone=f"1380000001{i}")
            for i in range(1, 5)
        ]
        db.add_all(other_parents)
        db.flush()
        students = [
            Student(name="小明", class_name="六年级1班", grade=6, gender="男",
                    birth_year=2014, parent_id=parent.id, interests=["篮球", "科学"]),
            Student(name="小雨", class_name="六年级1班", grade=6, gender="女",
                    birth_year=2014, parent_id=other_parents[0].id),
            Student(name="小志", class_name="六年级1班", grade=6, gender="男",
                    birth_year=2013, parent_id=other_parents[1].id),
            Student(name="小蕊", class_name="六年级1班", grade=6, gender="女",
                    birth_year=2014, parent_id=other_parents[2].id),
            Student(name="小航", class_name="六年级1班", grade=6, gender="男",
                    birth_year=2014, parent_id=other_parents[3].id),
        ]
        db.add_all(students)
        db.flush()
        xiaoming = students[0]

        # ---------- 健康档案：小明三学期纵向（超重趋势+视力连续下滑 → 两条AI建议线） ----------
        db.add_all([
            HealthRecord(student_id=xiaoming.id, term="2024-2025上", height_cm=148.0,
                         weight_kg=45.5, vision_left=5.0, vision_right=5.0, dental_caries=1),
            HealthRecord(student_id=xiaoming.id, term="2024-2025下", height_cm=151.0,
                         weight_kg=50.0, vision_left=4.9, vision_right=5.0, dental_caries=1),
            HealthRecord(student_id=xiaoming.id, term="2025-2026上", height_cm=153.5,
                         weight_kg=54.8, vision_left=4.8, vision_right=4.9, dental_caries=0),
        ])
        # 同学健康档案（各1条，供桌椅匹配率演示：小志159.5cm偏高需2号桌）
        for s, h, w in [(students[1], 150.0, 41.0), (students[2], 159.5, 52.0),
                        (students[3], 146.0, 38.5), (students[4], 152.0, 47.0)]:
            db.add(HealthRecord(student_id=s.id, term="2025-2026上", height_cm=h,
                                weight_kg=w, vision_left=5.0, vision_right=4.9))

        # ---------- 体测档案：跳绳/肺活量弱项（→锻炼处方+选修课推荐因子），含AI视频计数来源 ----------
        db.add_all([
            FitnessRecord(student_id=xiaoming.id, term="2024-2025下", item="一分钟跳绳",
                          value=72, unit="个/分钟", score=60, source="manual"),
            FitnessRecord(student_id=xiaoming.id, term="2024-2025下", item="50米跑",
                          value=9.8, unit="秒", score=70, source="manual"),
            FitnessRecord(student_id=xiaoming.id, term="2025-2026上", item="一分钟跳绳",
                          value=78, unit="个/分钟", score=60, source="ai_video"),
            FitnessRecord(student_id=xiaoming.id, term="2025-2026上", item="50米跑",
                          value=9.5, unit="秒", score=70, source="manual"),
            FitnessRecord(student_id=xiaoming.id, term="2025-2026上", item="坐位体前屈",
                          value=14.5, unit="cm", score=90, source="manual"),
            FitnessRecord(student_id=xiaoming.id, term="2025-2026上", item="肺活量",
                          value=1850, unit="ml", score=70, source="manual"),
            FitnessRecord(student_id=xiaoming.id, term="2025-2026上", item="仰卧起坐",
                          value=33, unit="个/分钟", score=70, source="manual"),
        ])

        # ---------- 成绩等级（个人纵向对比，不排名） ----------
        for term, levels in [
            ("2024-2025下", {"语文": "良", "数学": "中", "英语": "良", "科学": "优"}),
            ("2025-2026上", {"语文": "良", "数学": "待提高", "英语": "良", "科学": "优"}),
        ]:
            db.add_all([
                AcademicRecord(student_id=xiaoming.id, term=term, subject=sub, level=lv)
                for sub, lv in levels.items()
            ])

        # ---------- 校外兴趣班：已在外学篮球 → 校内篮球课自动排除（推荐因子F5演示） ----------
        db.add(ExternalClass(student_id=xiaoming.id, category="体育",
                             name="XX篮球俱乐部周末班", weekly_hours=3))

        # ---------- 选修课目录（10门，覆盖5类；篮球满员/朗读已报名/周一双课演示时段冲突） ----------
        courses = [
            Course(name="花样跳绳", category="体育", teacher="体育组·孙老师", weekday=0,
                   time_slot="15:40-16:40", capacity=30, enrolled=12,
                   intro="国家体测重点项目专项课，AI视频计数辅助打卡"),
            Course(name="田径基础", category="体育", teacher="体育组·钱老师", weekday=2,
                   time_slot="15:40-16:40", capacity=25, enrolled=20,
                   intro="跑跳投基础，改善速度与耐力"),
            Course(name="校园篮球", category="体育", teacher="体育组·周老师", weekday=4,
                   time_slot="15:40-16:40", capacity=24, enrolled=24,
                   intro="小篮球规则，班级联赛"),
            Course(name="游泳启蒙(馆校合作)", category="体育", teacher="街道文体中心教练", weekday=3,
                   time_slot="15:40-17:00", capacity=20, enrolled=8,
                   intro="与街道文体中心合作课程，提升肺活量"),
            Course(name="数学思维游戏", category="科技", teacher="数学组·吴老师", weekday=0,
                   time_slot="15:40-16:40", capacity=30, enrolled=15,
                   intro="数独/逻辑推理/趣味建模，夯实数学基础"),
            Course(name="趣味编程入门", category="科技", teacher="信息组·郑老师", weekday=1,
                   time_slot="15:40-16:40", capacity=20, enrolled=18,
                   intro="图形化编程，做小游戏"),
            Course(name="科学实验站", category="科技", teacher="科学组·冯老师", weekday=3,
                   time_slot="15:40-16:40", capacity=24, enrolled=10,
                   intro="动手实验：光、电、水的奥秘"),
            Course(name="合唱团", category="艺术", teacher="音乐组·陈老师", weekday=1,
                   time_slot="15:40-16:40", capacity=40, enrolled=25,
                   intro="校合唱团梯队，区艺术节展演"),
            Course(name="经典朗读与演讲", category="人文", teacher="语文组·许老师", weekday=2,
                   time_slot="15:40-16:40", capacity=30, enrolled=9,
                   intro="AI朗读评测辅助纠音，提升表达自信"),
            Course(name="校园小农田", category="劳动", teacher="劳动组·何老师", weekday=4,
                   time_slot="15:40-16:40", capacity=20, enrolled=6,
                   intro="种植观察+劳动教育，收获归班级"),
        ]
        db.add_all(courses)
        db.flush()
        db.add(CourseEnrollment(course_id=courses[8].id, student_id=xiaoming.id,
                                reason="推荐理由快照：语文评价为「良」，朗读课提升表达；周二时段无冲突"))

        # ---------- 请假台账：历史2条已批 + 1条待审批（班主任审批流演示） ----------
        db.add_all([
            LeaveRequest(student_id=xiaoming.id,
                         start_date=(today - timedelta(days=40)).isoformat(),
                         end_date=(today - timedelta(days=39)).isoformat(),
                         days=2, leave_type="sick", symptoms=["发热", "咳嗽"],
                         note="流感就医", status="approved", approved_by="李老师"),
            LeaveRequest(student_id=xiaoming.id,
                         start_date=(today - timedelta(days=15)).isoformat(),
                         end_date=(today - timedelta(days=15)).isoformat(),
                         days=1, leave_type="personal", note="家庭事务",
                         status="approved", approved_by="李老师"),
            LeaveRequest(student_id=xiaoming.id,
                         start_date=(today + timedelta(days=1)).isoformat(),
                         end_date=(today + timedelta(days=1)).isoformat(),
                         days=1, leave_type="sick", symptoms=["咳嗽"],
                         note="夜间咳嗽加重，明日就医", status="pending"),
        ])

        # ---------- 用餐日历：本月勾选全部工作日（后付费，无余额） ----------
        month_str = today.strftime("%Y-%m")
        _, last_day = calendar.monthrange(today.year, today.month)
        workdays = [d for d in range(1, last_day + 1)
                    if datetime(today.year, today.month, d).weekday() < 5]
        for s in students:
            db.add(MealPlan(student_id=s.id, month=month_str, days=workdays,
                            price_per_meal=14))

        # ---------- 年检公示墙（7门类；含临期/超期/不合格演示自动提醒） ----------
        db.add_all([
            AssetInspection(target="翻新教室(六年级1班)", category="renovation",
                            item="甲醛/TVOC第三方检化验（CMA资质）",
                            result="甲醛0.05mg/m³、TVOC0.38mg/m³，均低于GB/T 18883限值",
                            report_no="JHY-2025-0817", inspect_date="2025-08-25",
                            next_due="2026-08-25", passed=True),
            AssetInspection(target="教学楼直饮水机(6台)", category="water",
                            item="滤芯更换与水质检测",
                            result="菌落总数/重金属合格，滤芯已全部更换",
                            report_no="SZJ-2025-1102",
                            inspect_date=(today - timedelta(days=80)).isoformat(),
                            next_due=(today + timedelta(days=10)).isoformat(), passed=True),
            AssetInspection(target="全校灭火器(96具)", category="fire",
                            item="压力表效期年检",
                            result="94具正常；2具压力不足已换新",
                            report_no=None,
                            inspect_date=(today - timedelta(days=200)).isoformat(),
                            next_due=(today - timedelta(days=5)).isoformat(), passed=True),
            AssetInspection(target="六年级1班教室", category="lighting",
                            item="课桌面照度检测（GB 7793≥300lx）",
                            result="平均照度412lx，黑板面564lx，合格",
                            report_no="ZD-2025-0901", inspect_date="2025-09-10",
                            next_due="2026-09-10", passed=True),
            AssetInspection(target="操场单双杠/攀爬架", category="sports",
                            item="螺栓紧固与锈蚀检查",
                            result="单双杠底座螺栓锈蚀2处，已停用待检修",
                            report_no=None,
                            inspect_date=(today - timedelta(days=20)).isoformat(),
                            next_due=(today + timedelta(days=160)).isoformat(), passed=False),
            AssetInspection(target="各班急救箱(30个)", category="medkit",
                            item="药品耗材效期盘点",
                            result="全部在效期内；碘伏棉签下月到期已列入采购",
                            report_no=None,
                            inspect_date=(today - timedelta(days=10)).isoformat(),
                            next_due=(today + timedelta(days=170)).isoformat(), passed=True),
            AssetInspection(target="六年级课桌椅", category="furniture",
                            item="GB/T 3976身高-型号匹配率抽检（联动体检身高）",
                            result="六年级1班匹配率80%，1名同学建议调整2号桌",
                            report_no=None,
                            inspect_date=(today - timedelta(days=5)).isoformat(),
                            next_due=(today + timedelta(days=360)).isoformat(), passed=True),
        ])

        # ---------- 通知（班级通知/家庭安全提示/资产闭环/教联体），含回执定向 ----------
        notifications = [
            Notification(title="【班级通知】明日校服日+带科学实验材料",
                         body="六年级1班：明天请穿校服；科学课请带上周发的实验材料包。",
                         level=NotifyLevel.info, audience_roles=["parent"],
                         audience_class="六年级1班", created_by="李老师"),
            Notification(title="【体测通知】下周三校内体测（跳绳/50米/坐位体前屈）",
                         body="请给孩子穿运动鞋。体测成绩自动进入孩子空间的体质档案，弱项会生成锻炼处方并联动选修课推荐。",
                         level=NotifyLevel.important, audience_roles=["parent"],
                         audience_class="六年级1班", created_by="李老师"),
            Notification(title="【资产闭环】六年级1班课桌椅更换已进入采购流程",
                         body="资产台账显示该班课桌椅2017年购置、成色2/5，年检身高匹配率80%。校务会已批准列入本学期采购计划。",
                         level=NotifyLevel.info, audience_roles=["parent", "teacher", "admin"],
                         created_by="赵校长"),
            Notification(title="【家庭安全提示】厨房用火用刀，请家长看护",
                         body="周末在家：燃气灶使用后关阀；刀具收纳远离孩子取用高度；教会孩子烫伤先冲冷水。"
                              "（本提示由学校推送给家长，校园AI不进入家庭场景）",
                         level=NotifyLevel.info, audience_roles=["parent"],
                         created_by="赵校长"),
            Notification(title="【教联体】街道文体中心游泳馆校合作课开放报名",
                         body="每周四放学后，教练由文体中心提供。可在选修课页查看孩子的个性化推荐。",
                         level=NotifyLevel.info, audience_roles=["parent", "teacher"],
                         created_by="赵校长"),
        ]
        db.add_all(notifications)
        db.flush()
        # 回执定向到人（收件箱按回执联查）
        all_users = [teacher, parent, community, admin] + other_parents
        for n in notifications:
            for u in all_users:
                if u.role.value in n.audience_roles and \
                        (not n.audience_class or u.class_name == n.audience_class):
                    db.add(NotificationReceipt(notification_id=n.id, user_id=u.id))

        db.commit()
        print("种子数据写入完成（v4）：")
        print(f"  用户{4 + len(other_parents)}（4角色演示账号+同班家长档案，无学生账号）")
        print(f"  学生档案{len(students)} / 设备{len(devices)} / 资产{len(assets)} / 选修课{len(courses)}")
        print(f"  共享空间{len(resources)} / 年检7门类 / 场馆点评3 / 通知{len(notifications)}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
