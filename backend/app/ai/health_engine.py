"""AI 引擎 · 健康成长分析（守医疗边界）

四条能力线（全部为规则引擎，依据公开国家标准/指南，可解释、可审计）：
- BMI 评价：依据 WS/T 586《学龄儿童青少年超重与肥胖筛查》分年龄性别界值（6-12岁简化表）
- 生长/视力纵向趋势：多学期体检记录 → 趋势判读（视力连续下滑即提示）
- 营养科普建议：依据《学龄儿童膳食指南(2022)》规则映射——只推送给自己家长，
  文案强制携带"营养科普提示，非医疗诊断"边界声明
- 体测国标折算 + 弱项锻炼处方：《国家学生体质健康标准》折算分 → 弱项生成处方并回流选修课推荐因子

AI 体测视频线：analyze_fitness_video() 与视觉引擎同思路——骨架关键点（MoveNet/RTMPose类）
姿态估计做动作计数与规范度判定，只保留关键点序列统计结果，原始视频即刻丢弃。
"""
import hashlib

# ---------- WS/T 586 简化界值表：{(年龄, 性别): (超重BMI, 肥胖BMI)} ----------
_BMI_CUT = {
    (6, "男"): (16.4, 17.7), (7, "男"): (17.0, 18.7), (8, "男"): (17.8, 19.7),
    (9, "男"): (18.5, 20.8), (10, "男"): (19.2, 21.9), (11, "男"): (19.9, 23.0),
    (12, "男"): (20.7, 24.1),
    (6, "女"): (16.2, 17.5), (7, "女"): (16.8, 18.5), (8, "女"): (17.6, 19.4),
    (9, "女"): (18.5, 20.4), (10, "女"): (19.5, 21.5), (11, "女"): (20.5, 22.7),
    (12, "女"): (21.5, 23.9),
}
# 消瘦下限（简化：各年龄段统一近似值，演示口径）
_BMI_THIN = {6: 13.2, 7: 13.4, 8: 13.6, 9: 13.8, 10: 14.2, 11: 14.6, 12: 15.1}


def bmi_status(age: int, gender: str, height_cm: float, weight_kg: float) -> dict:
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
    age = max(6, min(age, 12))
    overweight, obese = _BMI_CUT.get((age, gender), _BMI_CUT[(age, "男")])
    thin = _BMI_THIN[age]
    if bmi >= obese:
        status = "肥胖"
    elif bmi >= overweight:
        status = "超重"
    elif bmi < thin:
        status = "消瘦"
    else:
        status = "正常"
    return {"bmi": bmi, "status": status,
            "cutoffs": {"消瘦<": thin, "超重≥": overweight, "肥胖≥": obese},
            "basis": "WS/T 586《学龄儿童青少年超重与肥胖筛查》"}


# ---------- 视力趋势（5.0 记录法） ----------

def vision_trend(records: list[dict]) -> dict:
    """records: [{term, vision_left, vision_right}] 按时间升序"""
    pts = [(r["term"], r.get("vision_left"), r.get("vision_right"))
           for r in records if r.get("vision_left") is not None]
    if len(pts) < 2:
        return {"trend": "数据不足", "alert": False, "advice": None}
    worst = [min(l, r) for _, l, r in pts]
    declining = all(worst[i + 1] <= worst[i] for i in range(len(worst) - 1)) and worst[-1] < worst[0]
    below = worst[-1] < 5.0
    alert = declining or below
    advice = None
    if alert:
        advice = ("视力出现连续下滑趋势，" if declining else "最近一次视力低于5.0，") + \
                 "建议：①每天2小时以上户外活动；②连续用眼20分钟远眺20秒；③尽快到正规机构复查散瞳验光。"
    return {"trend": "连续下滑" if declining else ("低于5.0" if below else "平稳"),
            "latest": worst[-1], "alert": alert, "advice": advice,
            "basis": "《儿童青少年近视防控适宜技术指南》"}


# ---------- 营养科普建议（《学龄儿童膳食指南(2022)》规则映射） ----------

_NUTRITION_RULES = {
    "肥胖": ["控制含糖饮料与油炸食品，主食粗细搭配",
           "每天中高强度运动不少于1小时（可结合学校运动处方）",
           "保证睡眠：小学生每天10小时"],
    "超重": ["减少高能量零食，晚餐七八分饱",
           "增加日常活动量：步行上下学、课间走出教室"],
    "消瘦": ["保证一日三餐规律，适量增加优质蛋白（蛋/奶/瘦肉/豆制品）",
           "关注维生素D与钙的摄入（奶制品300ml/天以上，多晒太阳）",
           "如持续消瘦建议到儿科/儿保门诊评估"],
    "正常": ["继续保持食物多样、天天喝奶、足量饮水的好习惯"],
}
_DISCLAIMER = "【营养科普提示，非医疗诊断】依据《中国学龄儿童膳食指南(2022)》生成，具体健康问题请咨询医生。"


def nutrition_advice(bmi_result: dict, dental_caries: int = 0) -> dict:
    tips = list(_NUTRITION_RULES.get(bmi_result["status"], []))
    supplements = []
    if bmi_result["status"] == "消瘦":
        supplements = ["维生素D", "钙", "锌"]
    elif bmi_result["status"] in ("肥胖", "超重"):
        supplements = ["维生素D（控体重期间保证骨骼发育）"]
    if dental_caries > 0:
        tips.append(f"检出龋齿{dental_caries}颗：控制甜食频次，早晚含氟牙膏刷牙，及时就诊充填")
    return {"status": bmi_result["status"], "tips": tips,
            "suggest_supplements": supplements, "disclaimer": _DISCLAIMER}


# ---------- 体测：国标折算 + 弱项处方 ----------

# 简化国标表（六年级口径）：item → [(达标值, 分数)]，值越大越好；50米跑越小越好
_FITNESS_STANDARD = {
    "一分钟跳绳": [(140, 100), (120, 90), (100, 80), (80, 70), (60, 60), (0, 40)],
    "50米跑":    [(8.4, 100), (8.9, 90), (9.4, 80), (10.0, 70), (10.8, 60), (99, 40)],
    "坐位体前屈": [(16, 100), (13, 90), (10, 80), (7, 70), (4, 60), (-99, 40)],
    "肺活量":    [(2600, 100), (2300, 90), (2000, 80), (1700, 70), (1400, 60), (0, 40)],
    "仰卧起坐":  [(45, 100), (40, 90), (35, 80), (30, 70), (25, 60), (0, 40)],
}
_LOWER_BETTER = {"50米跑"}

# 弱项 → 锻炼处方（大课间/家庭可执行，对标"每天综合体育活动不低于2小时"）
_PRESCRIPTIONS = {
    "一分钟跳绳": "每天2组×1分钟计时跳绳（AI视频计数打卡），组间休息2分钟，两周后复测",
    "50米跑": "每周3次30米加速跑×6组 + 高抬腿2组×30秒，注意摆臂",
    "坐位体前屈": "每天睡前坐位体前屈静态拉伸3组×30秒，配合体前屈动态热身",
    "肺活量": "每周3次慢跑10分钟 + 吹气球练习，游泳类选修课优先",
    "仰卧起坐": "隔天仰卧起坐3组×15个，配合平板支撑2组×30秒",
}


def fitness_score(item: str, value: float) -> int:
    table = _FITNESS_STANDARD.get(item)
    if not table:
        return 0
    for cut, score in table:
        if (value <= cut) if item in _LOWER_BETTER else (value >= cut):
            return score
    return 40


def fitness_profile(records: list[dict]) -> dict:
    """最近一期体测 → 总评 + 弱项 + 锻炼处方。records: [{item, value, score}]"""
    if not records:
        return {"avg_score": None, "weak_items": [], "prescriptions": [], "strong_items": []}
    avg = round(sum(r["score"] for r in records) / len(records))
    weak = [r["item"] for r in records if r["score"] < 70]
    strong = [r["item"] for r in records if r["score"] >= 90]
    return {
        "avg_score": avg,
        "weak_items": weak,
        "strong_items": strong,
        "prescriptions": [{"item": w, "plan": _PRESCRIPTIONS.get(w, "加强针对性练习")} for w in weak],
        "basis": "《国家学生体质健康标准》折算（六年级口径）",
    }


# ---------- AI 体测视频：骨架关键点计数（演示回退实现） ----------

def analyze_fitness_video(video: bytes, item: str) -> dict:
    """视频 → {count/规范度/折算分}。生产路径为姿态估计模型（MoveNet/RTMPose）
    抽取骨架关键点序列做周期计数与动作规范判定；本演示环境用视频字节哈希
    生成确定性结果走完全相同的输出结构。原始视频推理后即丢弃，只存统计结果。
    """
    h = hashlib.sha256(video).digest()
    base = {"一分钟跳绳": (95, 45), "仰卧起坐": (28, 14), "开合跳": (40, 20)}.get(item, (50, 25))
    count = base[0] + h[0] % base[1]
    form_ok_ratio = round(0.75 + (h[1] % 20) / 100, 2)
    issues = []
    if form_ok_ratio < 0.85:
        issues = {"一分钟跳绳": ["起跳过高，重心不稳"], "仰卧起坐": ["借助惯性，肩胛未完全离地"],
                  "开合跳": ["双臂未过头顶"]}.get(item, [])
    return {
        "item": item,
        "count": count,
        "form_ok_ratio": form_ok_ratio,
        "form_issues": issues,
        "score": fitness_score(item, count) if item in _FITNESS_STANDARD else None,
        "keypoints_only": True,   # 只保留关键点统计，原始视频已丢弃
        "video_hash": hashlib.sha256(video).hexdigest()[:16],
    }
