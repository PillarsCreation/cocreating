"""AI 引擎 · 对话意图路由

角色感知的意图识别：不同角色可用意图不同（权限矩阵）；
意图并列时按"动作优先于查询"消歧。v4 意图覆盖安全域 + 平时服务域（健康/选课/请假/用餐）。
学生无账号：孩子相关意图全部由家长账号触达（孩子空间）。
"""
from ..models import UserRole

# 意图 → 关键词
_INTENT_KEYWORDS: dict[str, list[str]] = {
    "report_incident": ["上报", "举报", "反映", "随手拍", "拍照", "投诉"],
    "query_incident": ["工单", "进度", "处理得怎么样", "受理", "我报的"],
    "query_safety": ["接送", "放学", "几点", "错峰", "拥堵吗", "通学", "路线"],
    "query_hazard": ["风险", "预警", "积水", "内涝", "地震", "台风", "暴雨", "甲醛", "隐患", "安全"],
    "query_plan": ["预案", "停课", "居家", "疏散", "应急", "运行模式"],
    "query_canteen": ["食堂", "饭菜", "留样", "食安", "菜品"],
    "query_asset": ["桌椅", "课桌", "资产", "报修", "硬件", "设施", "年检", "淘汰"],
    "book_resource": ["预约场地", "借用", "申请场地", "订场", "停车"],
    "find_resource": ["场地", "资源", "活动室", "体育馆", "去哪", "车位", "避难"],
    "query_health": ["健康", "体检", "身高", "体重", "视力", "体测", "体质", "健康档案", "营养", "BMI", "锻炼"],
    "query_course": ["选修课", "选课", "课后服务", "兴趣班", "报名", "推荐课"],
    "ask_leave": ["请假", "病假", "事假", "发烧请", "不去上学"],
    "query_meal": ["饭费", "用餐", "订餐", "吃饭日", "账单", "缴费"],
}

# 并列时的优先级：动作类意图排在查询类之前
_INTENT_PRIORITY = [
    "report_incident", "book_resource", "ask_leave",
    "query_plan", "query_hazard", "query_canteen", "query_asset",
    "query_health", "query_course", "query_meal",
    "query_incident", "query_safety", "find_resource",
]

# 角色权限矩阵：该角色可触达的意图
# 家长账号内嵌孩子空间：健康/选课/请假/用餐意图归家长（学生无账号）
_ROLE_INTENTS: dict[UserRole, set[str]] = {
    UserRole.parent: {"report_incident", "query_incident", "query_safety",
                      "query_hazard", "query_plan", "query_canteen", "find_resource",
                      "query_health", "query_course", "ask_leave", "query_meal"},
    UserRole.teacher: {"report_incident", "query_incident", "query_safety", "query_hazard",
                       "query_plan", "query_canteen", "book_resource", "find_resource",
                       "ask_leave", "query_course"},
    UserRole.community: {"report_incident", "query_incident", "query_safety",
                         "query_hazard", "find_resource"},
    UserRole.admin: set(_INTENT_KEYWORDS.keys()),
}

_REPLIES: dict[str, str] = {
    "report_incident": "好的，请描述您发现的问题（位置+情况），我会自动分类并派单给对应的处置力量。您也可以直接使用「随手拍」页面。",
    "query_incident": "正在为您查询工单进度，可在「随手拍」页面查看全部状态流转记录。",
    "query_safety": "已为您调出接送安排与通学路况，注意查看当前推荐的儿童友好路线。",
    "query_hazard": "当前活跃风险事件如下（多模态信号交叉印证后确认），点击可查看完整推理链。",
    "query_plan": "当前校园运行模式与应急预案如下。预案矩阵全量公开，可在指挥页查看。",
    "query_canteen": "食堂食安公示板：留样合规率、冷链温度曲线与食安指数全部公开可查。",
    "query_asset": "资产台账与年检公示已调出：超龄资产淘汰建议、7门类年检效期一目了然。",
    "book_resource": "请告诉我场地/车位、日期与时段，系统会自动检测冲突并生成预约单。",
    "find_resource": "已为您检索共享空间目录（含应急状态下的避难点角色）。",
    "query_health": "孩子空间·健康档案已调出：多学期身高体重视力对比、体测弱项与锻炼处方（营养建议为科普提示、非医疗诊断）。",
    "query_course": "选修课推荐已按孩子的体测弱项、健康趋势、成绩与兴趣个性化排序，每条推荐都附理由，已在校外学的类别不重复推荐。",
    "ask_leave": "请在「请假」页选择日期与类型（病假请勾选症状标签），提交后班主任审批；批准的整天假会提示您确认是否取消当日用餐。",
    "query_meal": "用餐日历已调出：按月勾选用餐日，月末按实际天数账单、银行卡后付费，无需充值。",
    "fallback": "抱歉我还不理解这个问题。您可以询问：风险预警、应急预案、接送安排、食堂食安、孩子健康档案、选修课推荐、请假、用餐缴费、上报问题或预约场地。",
    "no_permission": "该功能不对当前角色开放。",
}


def detect_intent(role: UserRole, message: str) -> str:
    scores: dict[str, int] = {}
    for intent, keywords in _INTENT_KEYWORDS.items():
        s = sum(1 for kw in keywords if kw in message)
        if s > 0:
            scores[intent] = s
    if not scores:
        return "fallback"
    top = max(scores.values())
    tied = [i for i, s in scores.items() if s == top]
    best = min(tied, key=_INTENT_PRIORITY.index)
    if best not in _ROLE_INTENTS.get(role, set()):
        return "no_permission"
    return best


def build_reply(intent: str) -> str:
    return _REPLIES.get(intent, _REPLIES["fallback"])
