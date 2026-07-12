"""AI 引擎 · 选修课个性化推荐（千人千面 + 可解释）

六因子加权打分，每个孩子看到的课程排序不同，每条推荐附带理由（可解释留痕）：
  F1 体测弱项匹配（权重最高）：体育差 → 优先推荐对应体育选修课
  F2 健康趋势匹配：BMI 超重/肥胖 → 有氧类；视力下滑 → 户外类加分、屏幕类减分
  F3 成绩等级扬长补短：某科"待提高" → 该学科关联课程加分；"优" → 拓展类加分
  F4 兴趣意愿：家长代填的孩子兴趣标签命中课程类别/名称
  F5 校外兴趣班排除：已在校外学同类 → 标记 excluded 不重复推荐（家长仍可见原因）
  F6 硬约束：时段冲突（与已报课程同一时段）/名额已满 → 提示不入推荐位

防信息茧房：得分榜单外保留一条"探索推荐"——孩子从未接触过的类别中随机稳定取一门。
家长可关闭个性化（personalized=false 时按课程目录原序返回）。
"""
# 课程类别 ↔ 体测项目 → 匹配关系
_WEAK_ITEM_COURSE = {
    "一分钟跳绳": ["花样跳绳", "田径", "篮球", "足球"],
    "50米跑": ["田径", "足球", "篮球"],
    "坐位体前屈": ["武术", "体操", "舞蹈"],
    "肺活量": ["游泳", "田径", "足球"],
    "仰卧起坐": ["武术", "体操", "田径"],
}
# 学科 → 关联课程关键词
_SUBJECT_COURSE = {
    "语文": ["朗读", "阅读", "写作", "书法"],
    "数学": ["思维", "数独", "编程"],
    "英语": ["英语", "戏剧"],
    "科学": ["科学", "编程", "机器人", "航模"],
}
# 项目词表：从校外兴趣班信息中提取"孩子已在学什么项目"，只排除同项目课程而非整个大类
# （校外学篮球 ≠ 排除全部体育课；跳绳/游泳等其他体育项目仍应可推荐）
_PROJECT_WORDS = ["篮球", "足球", "跳绳", "游泳", "田径", "舞蹈", "武术", "体操",
                  "乒乓", "羽毛球", "轮滑", "跆拳道", "围棋", "编程", "机器人",
                  "钢琴", "小提琴", "美术", "书法", "合唱", "朗读", "戏剧", "航模"]


def _extract_projects(texts) -> set[str]:
    found = set()
    for t in texts:
        found |= {w for w in _PROJECT_WORDS if w in (t or "")}
    return found


_OUTDOOR_KEYWORDS = ["田径", "足球", "篮球", "种植", "劳动", "定向越野"]
_SCREEN_KEYWORDS = ["编程", "机器人"]
_AEROBIC_KEYWORDS = ["田径", "足球", "篮球", "游泳", "跳绳", "定向越野"]


def recommend(courses: list[dict], profile: dict) -> list[dict]:
    """courses: CourseOut dict 列表
    profile: {
      weak_items: [体测弱项], strong_items: [...],
      bmi_status: 正常/超重/肥胖/消瘦, vision_alert: bool,
      academic: {学科: 等级}, interests: [兴趣标签],
      external_categories: {已在校外学的类别}, enrolled_slots: {(weekday,time_slot)},
      enrolled_course_ids: {已报课程id},
    }
    返回带 match_score/reasons/tag/excluded/conflict 的课程列表，推荐位在前。
    """
    weak = profile.get("weak_items", [])
    bmi_status = profile.get("bmi_status", "正常")
    vision_alert = profile.get("vision_alert", False)
    academic = profile.get("academic", {})
    interests = profile.get("interests") or []
    external = profile.get("external_categories", set())
    external_names = profile.get("external_names", [])
    ext_projects = _extract_projects(external_names)
    slots = profile.get("enrolled_slots", set())
    enrolled_ids = profile.get("enrolled_course_ids", set())

    scored = []
    for c in courses:
        score, reasons = 0, []
        name, cat = c["name"], c["category"]

        # F5 校外排除（先判：同项目课程不再累加其他理由；同大类不同项目仍正常推荐）
        hit = _extract_projects([name]) & ext_projects
        if hit:
            proj = "、".join(sorted(hit))
            scored.append({**c, "match_score": 0, "reasons":
                           [f"已登记校外「{proj}」兴趣班，不重复推荐（可手动报名）"],
                           "tag": None, "excluded": True, "conflict": None})
            continue

        # F1 体测弱项（权重最高 +40）
        for w in weak:
            if any(k in name for k in _WEAK_ITEM_COURSE.get(w, [])):
                score += 40
                reasons.append(f"体测「{w}」待加强，本课直接针对该项（锻炼处方联动）")
                break

        # F2 健康趋势 ±15
        if bmi_status in ("超重", "肥胖") and any(k in name for k in _AEROBIC_KEYWORDS):
            score += 15
            reasons.append(f"体格评价为{bmi_status}，推荐有氧运动类课程")
        if vision_alert:
            if any(k in name for k in _OUTDOOR_KEYWORDS):
                score += 15
                reasons.append("视力有下滑趋势，户外课程有助于近视防控")
            if any(k in name for k in _SCREEN_KEYWORDS):
                score -= 10
                reasons.append("视力防控期间适当控制屏幕类课程时长")

        # F3 成绩扬长补短 +20/+10
        for subject, level in academic.items():
            kws = _SUBJECT_COURSE.get(subject, [])
            if any(k in name for k in kws):
                if level == "待提高":
                    score += 20
                    reasons.append(f"{subject}评价为「待提高」，本课可夯实基础")
                elif level == "优":
                    score += 10
                    reasons.append(f"{subject}评价为「优」，可向拓展方向发展")
                break

        # F4 兴趣意愿 +25
        for tag in interests:
            if tag in name or tag == cat:
                score += 25
                reasons.append(f"命中孩子兴趣「{tag}」")
                break

        # F6 硬约束
        conflict = None
        if c["id"] in enrolled_ids:
            conflict = "已报名本课"
        elif (c["weekday"], c["time_slot"]) in slots:
            conflict = "与已报课程时段冲突"
        elif c["enrolled"] >= c["capacity"]:
            conflict = "名额已满"

        scored.append({**c, "match_score": score, "reasons": reasons,
                       "tag": None, "excluded": False, "conflict": conflict})

    # 排序：无冲突者按得分降序；有冲突/排除沉底
    def sort_key(x):
        blocked = x["excluded"] or x["conflict"] is not None
        return (blocked, -x["match_score"], x["id"])
    scored.sort(key=sort_key)

    # 打标：前3且得分>0 为优先推荐
    top = 0
    for x in scored:
        if not x["excluded"] and x["conflict"] is None and x["match_score"] > 0 and top < 3:
            x["tag"] = "优先推荐"
            top += 1

    # 防茧房探索推荐：孩子未接触类别（非兴趣/非校外/非已推荐）里稳定取一门
    touched = set(external) | {t for t in interests} | \
              {x["category"] for x in scored if x["tag"] == "优先推荐"}
    explore_pool = [x for x in scored
                    if x["category"] not in touched and not x["excluded"]
                    and x["conflict"] is None and x["tag"] is None]
    if explore_pool:
        pick = min(explore_pool, key=lambda x: x["id"])   # 确定性选取，演示可复现
        pick["tag"] = "探索推荐"
        pick["reasons"].append("孩子还没接触过这一类，跨领域体验有助于发现新兴趣")
    return scored
