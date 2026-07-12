"""v4 核心测试：安全四层架构全链路 + 教联体平时服务线

急时：认证(4角色) / 感知(遥测+帧) / 认知(本体融合+缺勤聚集+楼梯拥挤) / 决策(预案+图算法)
     / 处置(工单+通知回执+资产权限+食安) / 场景注入端到端(去日期化命名)
平时：孩子空间(健康/体测/营养边界/隐私) / 选修课AI推荐(六因子可解释) / 请假台账(审批+统计+聚集预警)
     / 用餐日历(勾选+账单+备餐) / 年检公示(效期+淘汰+桌椅匹配) / 场馆点评(口碑+差评)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["REDGATE_DB_URL"] = "sqlite:///./test_redgate.db"

from fastapi.testclient import TestClient

# 测试库初始化（先删旧库再导入 app）
_db = Path(__file__).resolve().parent.parent / "test_redgate.db"
if _db.exists():
    _db.unlink()

from app.main import app  # noqa: E402
import seed  # noqa: E402

seed.seed()
client = TestClient(app)

# 种子ID约定：1李老师(teacher) 2王女士(parent) 3张主任(community) 4赵校长(admin)
TEACHER, PARENT, COMMUNITY, ADMIN = 1, 2, 3, 4


def _xiaoming_id():
    kids = client.get(f"/api/children/by-parent/{PARENT}").json()
    return kids[0]["id"]


# ---------- 认证（4角色，无学生账号） ----------

def test_login_ok():
    r = client.post("/api/auth/login", json={"username": "parent", "password": "123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "parent" and body["name"] == "王女士"


def test_login_wrong_password():
    r = client.post("/api/auth/login", json={"username": "parent", "password": "bad"})
    assert r.status_code == 401


def test_demo_accounts_no_student_no_password():
    r = client.get("/api/auth/accounts")
    assert r.status_code == 200
    accounts = r.json()
    assert len(accounts) == 4
    assert {a["username"] for a in accounts} == {"teacher", "parent", "community", "admin"}
    assert all("password" not in a for a in accounts)


# ---------- 感知层 ----------

def test_devices_registered():
    r = client.get("/api/perception/devices")
    assert r.status_code == 200
    ids = {d["device_id"] for d in r.json()}
    assert "iot-water-eastgate-01" in ids and "cam-stair-g6-01" in ids


def test_telemetry_threshold_anomaly():
    r = client.post("/api/perception/telemetry",
                    json={"device_id": "iot-noise-eastgate-01",
                          "metric": "noise_db", "value": 85})
    assert r.status_code == 201
    assert r.json()["is_anomaly"] is True


def test_frame_ingest_discards_raw():
    r = client.post("/api/perception/frames",
                    data={"device_id": "cam-eastgate-01", "hint": "illegal_parking"},
                    files={"frame": ("f.jpg", os.urandom(2048), "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["frame_bytes_discarded"] is True
    assert any(e["event_type"] == "illegal_parking" for e in body["events"])


# ---------- 认知层：本体融合 ----------

def test_ontology_view():
    r = client.get("/api/brain/ontology")
    assert r.status_code == 200
    classes = {c["class"]: c for c in r.json()["classes"]}
    assert classes["waterlogging"]["path"] == ["waterlogging", "WeatherHazard", "Hazard"]
    assert classes["illness_cluster"]["path"] == ["illness_cluster", "HealthHazard", "Hazard"]
    assert classes["stair_crowding"]["path"] == ["stair_crowding", "CrowdHazard", "Hazard"]


def test_single_modality_no_hazard():
    """单一模态信号不告警（防误报）"""
    from app.ai.ontology import fuse
    hazards = fuse([{"modality": "sensor", "key": "water_level_cm", "value": 20,
                     "zone": "东门下凹路段", "ref": "t"}])
    assert not any(h["hazard_class"] == "waterlogging" for h in hazards)


def test_cross_modality_confirms_hazard():
    from app.ai.ontology import fuse
    hazards = fuse([
        {"modality": "sensor", "key": "water_level_cm", "value": 20, "zone": "东门下凹路段", "ref": "w1"},
        {"modality": "official", "key": "rainstorm", "level": "orange", "ref": "o1"},
    ])
    match = [h for h in hazards if h["hazard_class"] == "waterlogging"]
    assert len(match) == 1
    assert match[0]["severity"] == 4
    assert "R-WATERLOG" in match[0]["inference"]


def test_stair_crowding_needs_two_modalities():
    """楼梯拥挤：仅噪音超限不告警；加视觉密度双模态印证才确认"""
    from app.ai.ontology import fuse
    only_noise = fuse([{"modality": "sensor", "key": "stair_noise_db", "value": 80,
                        "zone": "六年级教学楼·楼梯间", "ref": "n1"}])
    assert not any(h["hazard_class"] == "stair_crowding" for h in only_noise)
    both = fuse([
        {"modality": "sensor", "key": "stair_noise_db", "value": 80,
         "zone": "六年级教学楼·楼梯间", "ref": "n1"},
        {"modality": "vision", "key": "stair_crowding",
         "zone": "六年级教学楼·楼梯间", "ref": "v1"},
    ])
    assert any(h["hazard_class"] == "stair_crowding" for h in both)


# ---------- 决策层 ----------

def test_plan_matrix_public():
    r = client.get("/api/brain/plan/matrix")
    assert r.status_code == 200
    combos = {(p["alert_type"], p["alert_level"]) for p in r.json()}
    assert ("rainstorm", "red") in combos and ("earthquake", "warning") in combos


def test_alert_activates_plan_and_monotonic():
    r = client.post("/api/brain/alerts", json={"alert_type": "rainstorm", "alert_level": "yellow"})
    assert r.status_code == 200 and r.json()["mode"] == "staggered"
    r2 = client.post("/api/brain/alerts", json={"alert_type": "rainstorm", "alert_level": "blue"})
    assert r2.json() is None
    r3 = client.post("/api/brain/alerts", json={"alert_type": "rainstorm", "alert_level": "orange"})
    assert r3.json()["mode"] == "indoor"
    client.post("/api/brain/plan/reset")
    assert client.get("/api/brain/plan/current").json()["mode"] == "normal"


def test_evacuation_routes_avoid_hazard():
    from app.ai.route_engine import evacuation_routes
    normal = {r["from"]: r for r in evacuation_routes()}
    assert "六年级教学楼" in normal
    risky = {r["from"]: r for r in evacuation_routes({"操场": 4})}
    assert risky["六年级教学楼"]["goal"] == "文体中心" or \
        risky["六年级教学楼"]["cost_m"] > normal["六年级教学楼"]["cost_m"]


def test_commute_scores():
    r = client.get("/api/brain/routes/commute")
    scores = {x["name"]: x for x in r.json()}
    assert scores["东门→下凹路段→理想城"]["score"] < scores["东门→京开辅路口→理想城"]["score"]


# ---------- 处置层：工单 / 通知 ----------

def test_incident_flood_classified_and_dispatched():
    r = client.post("/api/incidents", json={
        "reporter_id": PARENT, "description": "东门下凹路段积水没过脚踝，孩子过不去",
        "location": "东门下凹路段"})
    assert r.status_code == 201
    body = r.json()
    assert body["category"] == "flood" and body["priority"] == 1


def test_incident_state_machine():
    r = client.post("/api/incidents", json={
        "reporter_id": PARENT, "description": "南门垃圾乱堆", "location": "南门"})
    no = r.json()["ticket_no"]
    bad = client.patch(f"/api/incidents/{no}/status",
                       json={"to_status": "closed", "operator": "t"})
    assert bad.status_code == 400
    ok = client.patch(f"/api/incidents/{no}/status",
                      json={"to_status": "processing", "operator": "t"})
    assert ok.status_code == 200


def test_notification_receipts():
    r = client.post("/api/notifications", json={
        "title": "测试通知", "body": "内容", "level": "important",
        "audience_roles": ["community"], "created_by": "test"})
    assert r.status_code == 201
    nid = r.json()["id"]
    stats = client.get(f"/api/notifications/{nid}/receipts").json()
    assert stats["total"] == 1 and stats["unread"] == 1   # 张主任
    inbox = client.get(f"/api/notifications/inbox/{COMMUNITY}").json()
    assert any(n["id"] == nid for n in inbox)
    client.post(f"/api/notifications/{nid}/read/{COMMUNITY}")
    assert client.get(f"/api/notifications/{nid}/receipts").json()["read"] == 1


# ---------- 处置层：资产权限（校长专属）/ 食安 ----------

def test_assets_admin_only():
    """资产台账归口校长：老师/家长403，校长200"""
    denied = client.get("/api/assets", params={"operator_id": TEACHER})
    assert denied.status_code == 403
    denied2 = client.get("/api/assets-summary", params={"operator_id": PARENT})
    assert denied2.status_code == 403
    ok = client.get("/api/assets", params={"operator_id": ADMIN})
    assert ok.status_code == 200
    codes = {a["code"] for a in ok.json()}
    assert "AS-G6C1-DESK" in codes
    summary = client.get("/api/assets-summary", params={"operator_id": ADMIN})
    assert summary.json()[0]["grade"] == 6   # 六年级成色最差排最前


def test_asset_qr_report_any_role():
    """扫码报修不受台账权限限制：老师发现坏损可直接报"""
    r = client.post("/api/assets/AS-G6-DESK/report",
                    json={"reporter_id": TEACHER, "description": "课桌腿松动摇晃"})
    assert r.status_code == 201
    assert r.json()["category"] == "facility" and r.json()["ref"] == "AS-G6-DESK"


def test_canteen_board():
    r = client.get("/api/canteen/board")
    assert r.status_code == 200
    body = r.json()
    assert "food_safety_index" in body and body["sample_compliance_rate"] > 0


# ---------- 共享空间 / 预约权限 ----------

def test_parking_realtime():
    r = client.get("/api/resources/parking")
    lots = r.json()
    assert len(lots) == 2 and all(lot["free"] is not None for lot in lots)


def test_emergency_map():
    roles = {x["emergency_role"] for x in client.get("/api/resources/emergency-map").json()}
    assert "应急避难点" in roles


def test_booking_permission_matrix():
    """社区侧不能发起预约只能审批；家长不能审批；教师发起→社区批准闭环"""
    forbidden = client.post("/api/resources/bookings", json={
        "resource_id": 2, "user_id": COMMUNITY, "date": "2026-09-11",
        "start_time": "10:00", "end_time": "11:00", "purpose": "社区不应能预约", "attendees": 5})
    assert forbidden.status_code == 403
    ok = client.post("/api/resources/bookings", json={
        "resource_id": 2, "user_id": TEACHER, "date": "2026-09-11",
        "start_time": "10:00", "end_time": "11:00", "purpose": "家长课堂", "attendees": 30})
    assert ok.status_code == 201 and ok.json()["status"] == "pending"
    no = ok.json()["booking_no"]
    deny = client.patch(f"/api/resources/bookings/{no}/status",
                        params={"status": "confirmed", "operator_id": PARENT})
    assert deny.status_code == 403
    approve = client.patch(f"/api/resources/bookings/{no}/status",
                           params={"status": "confirmed", "operator_id": COMMUNITY})
    assert approve.status_code == 200 and approve.json()["status"] == "confirmed"


def test_booking_conflict():
    ok = client.post("/api/resources/bookings", json={
        "resource_id": 1, "user_id": TEACHER, "date": "2026-09-10",
        "start_time": "16:00", "end_time": "17:00", "purpose": "应急演练", "attendees": 50})
    assert ok.status_code == 201
    dup = client.post("/api/resources/bookings", json={
        "resource_id": 1, "user_id": TEACHER, "date": "2026-09-10",
        "start_time": "16:30", "end_time": "17:30", "purpose": "冲突测试", "attendees": 10})
    assert dup.status_code == 409


# ---------- 对话路由 ----------

def test_chat_hazard_intent():
    r = client.post("/api/chat", json={"role": "parent", "message": "现在有什么风险预警吗"})
    assert r.json()["intent"] == "query_hazard"


def test_chat_parent_health_and_leave_intents():
    r = client.post("/api/chat", json={"role": "parent", "message": "孩子这学期体测怎么样"})
    assert r.json()["intent"] == "query_health"
    r2 = client.post("/api/chat", json={"role": "parent", "message": "明天想给孩子请假"})
    assert r2.json()["intent"] == "ask_leave"


def test_chat_role_permission():
    """社区角色无预约发起权限"""
    r = client.post("/api/chat", json={"role": "community", "message": "我要预约场地"})
    assert r.json()["intent"] == "no_permission"


# ---------- 孩子空间（一人一档不一人一号） ----------

def test_children_of_parent():
    kids = client.get(f"/api/children/by-parent/{PARENT}").json()
    assert len(kids) == 1 and kids[0]["name"] == "小明"
    assert kids[0]["class_name"] == "六年级1班"


def test_child_profile_full():
    sid = _xiaoming_id()
    r = client.get(f"/api/children/{sid}/profile", params={"operator_id": PARENT})
    assert r.status_code == 200
    body = r.json()
    # 健康纵向：3学期
    assert len(body["health_records"]) == 3
    # BMI：153.5cm/54.8kg 12岁男孩 → 超重/肥胖区间
    assert body["bmi"]["status"] in ("超重", "肥胖")
    # 视力连续下滑 → 预警+建议
    assert body["vision"]["alert"] is True and body["vision"]["advice"]
    # 营养建议守医疗边界：强制免责声明 + 维生素建议
    assert "非医疗诊断" in body["nutrition"]["disclaimer"]
    # 体测弱项 → 锻炼处方
    assert "一分钟跳绳" in body["fitness"]["weak_items"]
    assert any(p["item"] == "一分钟跳绳" for p in body["fitness"]["prescriptions"])
    # 成绩等级存在且不含排名字段
    assert body["academic"] and all("rank" not in a for a in body["academic"])


def test_child_profile_privacy():
    """其他家长不能看小明的档案（隐私边界）"""
    sid = _xiaoming_id()
    other_parent = 5   # 种子中的六1家长1
    r = client.get(f"/api/children/{sid}/profile", params={"operator_id": other_parent})
    assert r.status_code == 403
    # 班主任（同班）可以看
    ok = client.get(f"/api/children/{sid}/profile", params={"operator_id": TEACHER})
    assert ok.status_code == 200


def test_fitness_video_ai_count():
    """AI体测：视频→计数落库（只存统计不存视频）"""
    sid = _xiaoming_id()
    r = client.post(f"/api/children/{sid}/fitness-video",
                    params={"operator_id": PARENT},
                    data={"item": "一分钟跳绳", "term": "2025-2026上"},
                    files={"video": ("v.mp4", os.urandom(8192), "video/mp4")})
    assert r.status_code == 200
    body = r.json()
    assert body["video_discarded"] is True and body["count"] > 0
    profile = client.get(f"/api/children/{sid}/profile", params={"operator_id": PARENT}).json()
    assert any(rec["source"] == "ai_video" for rec in profile["fitness"]["records"])


# ---------- 选修课AI推荐 ----------

def test_course_recommendation_explainable():
    sid = _xiaoming_id()
    r = client.get("/api/courses", params={"student_id": sid, "operator_id": PARENT})
    assert r.status_code == 200
    courses = r.json()
    by_name = {c["name"]: c for c in courses}
    # F1 体测弱项：跳绳弱 → 花样跳绳应为优先推荐且带理由
    jump = by_name["花样跳绳"]
    assert jump["tag"] == "优先推荐"
    assert any("跳绳" in reason for reason in jump["reasons"])
    # F5 校外排除：已在校外学篮球 → 校园篮球标记排除
    basketball = by_name["校园篮球"]
    assert basketball["excluded"] is True
    # 推荐排序：优先推荐在目录序前面
    assert courses[0]["match_score"] >= courses[1]["match_score"]
    # 探索推荐存在（防信息茧房）
    assert any(c["tag"] == "探索推荐" for c in courses)
    # 家长可关闭个性化 → 原序无标签
    plain = client.get("/api/courses", params={"personalized": False}).json()
    assert all(c["match_score"] == 0 and c["tag"] is None for c in plain)


def test_course_enroll_conflict_and_capacity():
    sid = _xiaoming_id()
    # 报名花样跳绳（周一）
    ok = client.post("/api/courses/1/enroll",
                     json={"student_id": sid, "operator_parent_id": PARENT,
                           "reason": "体测弱项推荐"})
    assert ok.status_code == 201
    # 同时段（周一）数学思维游戏 → 409冲突
    conflict = client.post("/api/courses/5/enroll",
                           json={"student_id": sid, "operator_parent_id": PARENT})
    assert conflict.status_code == 409
    # 满员课校园篮球 → 409
    full = client.post("/api/courses/3/enroll",
                       json={"student_id": sid, "operator_parent_id": PARENT})
    assert full.status_code == 409
    # 其他家长不能替小明报名
    other = client.post("/api/courses/2/enroll",
                        json={"student_id": sid, "operator_parent_id": 5})
    assert other.status_code == 403
    # 报名列表含理由快照
    mine = client.get(f"/api/courses/enrollments/{sid}",
                      params={"operator_id": PARENT}).json()
    assert any(e["name"] == "花样跳绳" and e["reason_snapshot"] for e in mine)
    # 退课恢复名额
    cancel = client.post("/api/courses/1/cancel",
                         json={"student_id": sid, "operator_parent_id": PARENT})
    assert cancel.status_code == 200


# ---------- 请假台账 ----------

def test_leave_flow_and_stats():
    sid = _xiaoming_id()
    # 病假必须带症状标签
    bad = client.post("/api/leave", json={
        "student_id": sid, "parent_id": PARENT, "start_date": "2026-09-14",
        "end_date": "2026-09-14", "leave_type": "sick"})
    assert bad.status_code == 400
    # 家长发起
    ok = client.post("/api/leave", json={
        "student_id": sid, "parent_id": PARENT, "start_date": "2026-09-14",
        "end_date": "2026-09-15", "leave_type": "sick", "symptoms": ["发热"]})
    assert ok.status_code == 201 and ok.json()["days"] == 2.0
    lid = ok.json()["id"]
    # 其他家长不能替小明请假
    other = client.post("/api/leave", json={
        "student_id": sid, "parent_id": 5, "start_date": "2026-09-14",
        "end_date": "2026-09-14", "leave_type": "personal"})
    assert other.status_code == 403
    # 班主任待办可见
    pending = client.get("/api/leave/pending", params={"operator_id": TEACHER}).json()
    assert any(p["id"] == lid for p in pending)
    # 家长不能审批
    deny = client.post(f"/api/leave/{lid}/approve",
                       json={"operator_id": PARENT, "approve": True})
    assert deny.status_code == 403
    # 班主任批准
    approve = client.post(f"/api/leave/{lid}/approve",
                          json={"operator_id": TEACHER, "approve": True})
    assert approve.status_code == 200 and approve.json()["status"] == "approved"
    # 班级统计：班主任首次能答上"每生请了几天假"
    stats = client.get("/api/leave/class-stats",
                       params={"class_name": "六年级1班", "operator_id": TEACHER}).json()
    xm = [s for s in stats["stats"] if s["student_name"] == "小明"][0]
    assert xm["term_days"] >= 3   # 种子2条+本条


def test_illness_cluster_alert():
    """缺勤聚集：注入3例同症状病假 → 看板告警 + 融合产生风险事件"""
    client.post("/api/brain/plan/reset")
    r = client.post("/api/scenario/illness_cluster")
    assert r.status_code == 200
    watch = client.get("/api/leave/illness-watch", params={"operator_id": ADMIN}).json()
    c61 = [c for c in watch["classes"] if c["class_name"] == "六年级1班"][0]
    assert any(s["alert"] for s in c61["symptoms"])
    hazards = client.get("/api/brain/hazards").json()
    assert any(h["hazard_class"] == "illness_cluster" for h in hazards)


# ---------- 用餐日历 ----------

def test_meal_calendar_and_bill():
    sid = _xiaoming_id()
    # 覆盖10月计划：勾选5个工作日
    ok = client.put("/api/meals/plan", json={
        "student_id": sid, "parent_id": PARENT,
        "month": "2026-10", "days": [12, 13, 14, 15, 16]})
    assert ok.status_code == 200
    # 周末日期被拒
    weekend = client.put("/api/meals/plan", json={
        "student_id": sid, "parent_id": PARENT,
        "month": "2026-10", "days": [10, 11]})
    assert weekend.status_code == 400
    # 账单预览：5天×14元，后付费无余额
    bill = client.get(f"/api/meals/bill/{sid}/2026-10",
                      params={"operator_id": PARENT}).json()
    assert bill["days_count"] == 5 and bill["amount"] == 70.0
    assert "后付费" in bill["payment"]
    # 其他家长不能改小明的日历
    other = client.put("/api/meals/plan", json={
        "student_id": sid, "parent_id": 5, "month": "2026-10", "days": [12]})
    assert other.status_code == 403


def test_kitchen_forecast():
    """食堂按用餐日历备餐：工作日各班人数可查"""
    r = client.get("/api/meals/kitchen-forecast", params={"date": "2026-10-13"})
    assert r.status_code == 200
    # 上面测试给小明勾了10-13；种子只给当月勾选，此处至少含小明1人
    assert r.json()["total"] >= 1


# ---------- 年检公示 / 淘汰清单 / 桌椅匹配 ----------

def test_inspection_wall_alerts():
    r = client.get("/api/inspections").json()
    assert r["summary"]["total"] >= 7
    cats = set(r["summary"]["categories"])
    assert {"renovation", "water", "fire", "lighting", "sports", "medkit", "furniture"} <= cats
    # 种子含超期灭火器+临期滤芯+不合格单双杠 → 提醒非空
    assert any("超期" in a for a in r["alerts"])
    assert any("临期" in a for a in r["alerts"])
    assert any("不合格" in a for a in r["alerts"])


def test_retirement_list():
    r = client.get("/api/inspections/retirement-list").json()
    codes = {x["code"] for x in r}
    assert "AS-G6C1-DESK" in codes and "AS-SPORT-RACK" in codes
    assert "AS-G1G5-DESK" not in codes   # 2021年购置成色4，不该出现


def test_desk_fit_privacy():
    r = client.get("/api/inspections/desk-fit").json()
    assert r["fit_rate"] is not None and 0 < r["fit_rate"] < 1
    # 小志159.5cm超出3号桌范围 → 建议2号桌；公示不含身高数值
    assert any("2号桌" in x["suggest"] for x in r["need_adjust"])
    assert all("height" not in x for x in r["need_adjust"])


# ---------- 场馆点评 ----------

def test_venue_reviews_and_reputation():
    # 家长不能点评（仅带队教师/校长）
    deny = client.post("/api/venue-reviews", json={
        "resource_id": 1, "teacher_id": PARENT, "rating": 5,
        "comment": "家长不该能点评", "visit_date": "2026-06-01"})
    assert deny.status_code == 403
    ok = client.post("/api/venue-reviews", json={
        "resource_id": 1, "teacher_id": TEACHER, "rating": 4,
        "comment": "第二次带班，动线熟悉，饮水补给方便。", "visit_date": "2026-06-20"})
    assert ok.status_code == 201
    rep = client.get("/api/venue-reputation").json()
    by_name = {x["name"]: x for x in rep}
    # 创客空间有2星差评 → warning 提示后续教师规避
    assert by_name["科技园·青少年创客空间"]["warning"] is not None
    assert by_name["街道文体中心·篮球馆"]["avg_rating"] >= 4


# ---------- 场景注入端到端（去日期化命名） ----------

def test_scenario_list_no_dates():
    scenarios = client.get("/api/scenario").json()
    names = {s["name"] for s in scenarios}
    assert names == {"dismissal_rainstorm", "food_incident", "earthquake",
                     "air_renovation", "illness_cluster", "stair_crowding"}
    # 场景标签不含具体日期数字（去日期化）
    assert all(not any(ch.isdigit() for ch in s["label"]) for s in scenarios)


def test_scenario_dismissal_rainstorm_full_chain():
    client.post("/api/brain/plan/reset")
    r = client.post("/api/scenario/dismissal_rainstorm")
    assert r.status_code == 200
    assert client.get("/api/brain/plan/current").json()["mode"] == "indoor"
    hazards = client.get("/api/brain/hazards").json()
    match = [h for h in hazards if h["hazard_class"] == "waterlogging"]
    assert match and match[0]["severity"] == 4
    inbox = client.get(f"/api/notifications/inbox/{PARENT}").json()
    assert any("内涝" in n["title"] for n in inbox)
    client.post("/api/brain/plan/reset")


def test_scenario_earthquake_evacuate():
    client.post("/api/brain/plan/reset")
    r = client.post("/api/scenario/earthquake")
    assert r.status_code == 200
    assert client.get("/api/brain/plan/current").json()["mode"] == "evacuate"
    routes = client.get("/api/brain/routes/evacuation").json()["routes"]
    assert routes and all(x["goal"] in ("操场", "文体中心") for x in routes)
    client.post("/api/brain/plan/reset")


def test_scenario_stair_crowding():
    client.post("/api/brain/plan/reset")
    r = client.post("/api/scenario/stair_crowding")
    assert r.status_code == 200
    hazards = client.get("/api/brain/hazards").json()
    assert any(h["hazard_class"] == "stair_crowding" for h in hazards)


def test_hazard_lifecycle():
    hazards = client.get("/api/brain/hazards").json()
    if hazards:
        hid = hazards[0]["id"]
        r1 = client.post(f"/api/brain/hazards/{hid}/advance")
        assert r1.json()["status"] == "mitigating"
        r2 = client.post(f"/api/brain/hazards/{hid}/advance")
        assert r2.json()["status"] == "cleared"
