"""AI 引擎 · 工单智能分类与派单

设计说明：
- 默认使用规则+关键词加权分类器（离线可运行，演示无外部依赖）
- 预留 LLM 接口：设置 REDGATE_LLM_API_KEY 后自动切换大模型分类
- 派单规则映射西红门镇"红门管家"志愿服务体系与镇属执法力量
"""
import os
import re

from ..models import IncidentCategory

# 关键词权重表：命中一次记对应权重，取总分最高的类别
_KEYWORD_WEIGHTS: dict[IncidentCategory, list[tuple[str, float]]] = {
    IncidentCategory.traffic: [
        ("拥堵", 3), ("违停", 3), ("堵车", 3), ("接送", 2), ("车辆", 1),
        ("占道停车", 3), ("交通", 2), ("路口", 1), ("斑马线", 2), ("超速", 3),
        ("停车位", 2), ("停到路中间", 3),
    ],
    IncidentCategory.vendor: [
        ("游商", 3), ("摊贩", 3), ("小吃摊", 3), ("占道经营", 3), ("兜售", 2),
        ("三无食品", 3), ("烧烤", 2), ("叫卖", 2),
    ],
    IncidentCategory.fire_hazard: [
        ("电动车", 3), ("充电", 2), ("飞线", 3), ("消防", 3), ("易燃", 2),
        ("火灾", 3), ("烟头", 1), ("堵塞消防通道", 3), ("电瓶", 2),
    ],
    IncidentCategory.environment: [
        ("垃圾", 3), ("污水", 3), ("乱堆", 2), ("卫生死角", 3),
        ("杂物", 2), ("狗粪", 2), ("绿化", 1), ("噪音", 3), ("施工吵", 3),
    ],
    IncidentCategory.facility: [
        ("损坏", 3), ("破损", 3), ("井盖", 3), ("路灯", 2), ("护栏", 2),
        ("坑洼", 2), ("设施", 1), ("漏电", 3), ("松动", 2), ("桌椅", 3), ("桌子", 2), ("凳子", 2),
    ],
    IncidentCategory.food: [
        ("饭菜", 3), ("食堂", 3), ("异物", 3), ("虫", 3), ("玻璃茬", 3), ("变质", 3),
        ("拉肚子", 3), ("呕吐", 2), ("留样", 2), ("食品", 2), ("发霉", 3), ("头发", 2),
    ],
    IncidentCategory.air: [
        ("甲醛", 3), ("刺鼻", 3), ("异味", 2), ("刷漆", 3), ("装修味", 3),
        ("头晕", 2), ("通风", 1), ("翻新", 2), ("油漆", 3),
    ],
    IncidentCategory.flood: [
        ("积水", 3), ("内涝", 3), ("淹", 3), ("水漫", 3), ("排水", 2), ("下水道堵", 3),
    ],
}

# 派单映射：类别 → (承接方, 默认优先级)  1=紧急 2=普通 3=低
_DISPATCH_RULES: dict[IncidentCategory, tuple[str, int]] = {
    IncidentCategory.traffic: ("交通护学岗·红门管家", 1),
    IncidentCategory.vendor: ("镇城管执法队", 2),
    IncidentCategory.fire_hazard: ("消防安全网格员", 1),
    IncidentCategory.environment: ("环境整治·红门管家", 2),
    IncidentCategory.facility: ("总务处·后勤维修组", 2),
    IncidentCategory.food: ("食堂负责人+区市场监管所", 1),
    IncidentCategory.air: ("总务处+施工方", 1),
    IncidentCategory.flood: ("镇市政维修组", 1),
    IncidentCategory.other: ("综合受理台", 3),
}

# 紧急词：命中则优先级提升为 1
_URGENT_WORDS = ["受伤", "起火", "冒烟", "漏电", "倒塌", "危险", "孩子", "学生", "紧急", "中毒", "晕倒"]


def classify_incident(description: str) -> tuple[IncidentCategory, float]:
    """返回 (类别, 置信度 0-1)"""
    if os.getenv("REDGATE_LLM_API_KEY"):
        result = _classify_with_llm(description)
        if result is not None:
            return result

    scores: dict[IncidentCategory, float] = {}
    for category, pairs in _KEYWORD_WEIGHTS.items():
        s = sum(w for kw, w in pairs if kw in description)
        if s > 0:
            scores[category] = s

    if not scores:
        return IncidentCategory.other, 0.3

    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = round(min(0.5 + scores[best] / (total + 3) * 0.5, 0.98), 2)
    return best, confidence


def dispatch(category: IncidentCategory, description: str) -> tuple[str, int]:
    """返回 (承接方, 优先级)"""
    assignee, priority = _DISPATCH_RULES[category]
    if any(w in description for w in _URGENT_WORDS):
        priority = 1
    return assignee, priority


def _classify_with_llm(description: str) -> tuple[IncidentCategory, float] | None:
    """LLM 分类（可选增强）。失败时返回 None 回退到规则分类器。"""
    try:
        import httpx

        api_key = os.environ["REDGATE_LLM_API_KEY"]
        base_url = os.getenv("REDGATE_LLM_BASE_URL", "https://api.anthropic.com/v1/messages")
        model = os.getenv("REDGATE_LLM_MODEL", "claude-haiku-4-5-20251001")
        categories = ", ".join(c.value for c in IncidentCategory)
        resp = httpx.post(
            base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 50,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"将以下校园周边问题上报分类为其中之一：{categories}。"
                        f"只输出类别英文单词。\n上报内容：{description}"
                    ),
                }],
            },
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip().lower()
        match = re.search(r"[a-z_]+", text)
        if match and match.group() in IncidentCategory.__members__:
            return IncidentCategory(match.group()), 0.95
    except Exception:
        pass
    return None
