"""决策层 · 平急预案引擎

把北京市教委预警响应规则数字化为状态机：
  (预警类型, 预警级别) → 校园运行模式 + 动作清单
参考真实流程：2025-07 北京暴雨橙警期间市教委通知多校停课居家学习。
运行模式单调升级原则：应急期间只允许升级或人工确认后降级，防止预警抖动导致模式来回切换。
"""

# 运行模式（保护等级递增）
MODES = ["normal", "staggered", "indoor", "home_study", "evacuate"]
MODE_LABELS = {
    "normal": "正常运行",
    "staggered": "错峰接送",
    "indoor": "室内避险·延迟放学",
    "home_study": "停课·居家学习",
    "evacuate": "紧急疏散",
}

# 预警矩阵：(alert_type, level) → (mode, actions)
# actions 中 auto=True 的动作由智能体直接执行（发通知/改接送表/推疏散路线），False 的生成待办给责任人
_PLAN_MATRIX: dict[tuple[str, str], tuple[str, list[dict]]] = {
    ("rainstorm", "blue"): ("normal", [
        {"text": "值班室关注雨情，检查东门下凹路段排水口", "owner": "总务处", "auto": False},
        {"text": "向家长推送雨天接送提示（雨具/慢行）", "owner": "智能体", "auto": True},
    ]),
    ("rainstorm", "yellow"): ("staggered", [
        {"text": "启动错峰放学：低年级提前20分钟，按班级到点呼叫", "owner": "智能体", "auto": True},
        {"text": "护学岗雨天增援：东门+2人", "owner": "红门管家", "auto": False},
        {"text": "水位计切换高频上报（5分钟/次）", "owner": "智能体", "auto": True},
    ]),
    ("rainstorm", "orange"): ("indoor", [
        {"text": "全体学生室内等候，家长到校后分批呼叫交接", "owner": "德育处", "auto": False},
        {"text": "推送紧急通知（需回执）：放学改室内交接，请勿在校门口聚集", "owner": "智能体", "auto": True},
        {"text": "封闭东门下凹路段通道，接送改走南门高地路线", "owner": "红门管家", "auto": False},
        {"text": "同步镇城运中心：申请排水抢险力量待命", "owner": "智能体", "auto": True},
    ]),
    ("rainstorm", "red"): ("home_study", [
        {"text": "次日停课·居家学习，推送全员紧急通知并统计回执", "owner": "智能体", "auto": True},
        {"text": "未回执家庭列入电话补呼清单", "owner": "班主任", "auto": False},
        {"text": "在校滞留学生转移至二层以上教室", "owner": "校应急指挥组", "auto": False},
    ]),
    ("typhoon", "blue"): ("normal", [
        {"text": "巡查校门口广告牌/围挡/树木", "owner": "总务处", "auto": False},
    ]),
    ("typhoon", "yellow"): ("staggered", [
        {"text": "停止全部户外课程与大课间", "owner": "教务处", "auto": False},
        {"text": "错峰放学并提示家长避开高空坠物风险路段", "owner": "智能体", "auto": True},
    ]),
    ("typhoon", "orange"): ("indoor", [
        {"text": "室内避险，远离玻璃窗", "owner": "班主任", "auto": False},
        {"text": "推送紧急通知（需回执）", "owner": "智能体", "auto": True},
    ]),
    ("typhoon", "red"): ("home_study", [
        {"text": "停课·居家学习，全员通知+回执追踪", "owner": "智能体", "auto": True},
    ]),
    ("earthquake", "warning"): ("evacuate", [
        {"text": "预警倒计时广播：就近伏地掩护（伏地、遮挡、手抓牢）", "owner": "智能体", "auto": True},
        {"text": "震动结束后按最优疏散路线撤离至操场避难点", "owner": "校应急指挥组", "auto": False},
        {"text": "推送家长紧急通知：学生正在有序疏散，请勿涌向校门", "owner": "智能体", "auto": True},
        {"text": "按班级清点人数并回报缺勤名单", "owner": "班主任", "auto": False},
    ]),
    ("heat", "orange"): ("staggered", [
        {"text": "停止户外体育课，调整放学至阴凉时段", "owner": "教务处", "auto": False},
        {"text": "推送防暑提示", "owner": "智能体", "auto": True},
    ]),
    ("air_pollution", "orange"): ("indoor", [
        {"text": "停止户外活动，启动教室新风/空气净化", "owner": "总务处", "auto": False},
        {"text": "推送家长通知：今日室内放学交接", "owner": "智能体", "auto": True},
    ]),
}


def resolve_plan(alert_type: str, alert_level: str) -> tuple[str, list[dict]] | None:
    """查预警矩阵；未命中的低级别预警返回 None（维持当前模式）"""
    return _PLAN_MATRIX.get((alert_type, alert_level))


def mode_rank(mode: str) -> int:
    return MODES.index(mode) if mode in MODES else 0


def is_upgrade(current: str, new: str) -> bool:
    return mode_rank(new) > mode_rank(current)


def matrix_view() -> list[dict]:
    """给前端展示完整预警矩阵（预案透明本身就是对家长的承诺）"""
    return [
        {
            "alert_type": t, "alert_level": lv, "mode": mode,
            "mode_label": MODE_LABELS[mode],
            "actions": actions,
        }
        for (t, lv), (mode, actions) in _PLAN_MATRIX.items()
    ]
