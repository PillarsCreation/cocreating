"""认知层 · 校园安全轻量本体框架（Ontology）

三部分组成：
- T-Box：风险类层级（subClassOf，支持传递闭包推理）与处置知识（mitigatedBy / responsibleParty / notifyLevel）
- A-Box：校园区域个体及属性（是否校门区/易涝/翻新中/后厨等）
- 规则库：多模态信号交叉印证规则 —— 单一信号不告警，独立模态达到阈值数量才生成融合风险事件，
  每次推理输出完整可解释推理链（信号→本体路径→规则→处置建议）

不依赖外部推理机：三元组存储 + 前向链推理，约束在校园安全这个封闭域内是充分的；
如需接入 OWL 生态，T-Box/A-Box 可直接导出为 RDF 三元组。
"""
from datetime import datetime, timedelta

# ---------- T-Box：类层级 ----------

_SUBCLASS: list[tuple[str, str]] = [
    ("WeatherHazard", "Hazard"),
    ("GeoHazard", "Hazard"),
    ("HealthHazard", "Hazard"),
    ("UrbanHazard", "Hazard"),
    ("FacilityHazard", "Hazard"),
    ("CrowdHazard", "Hazard"),
    ("waterlogging", "WeatherHazard"),      # 校门积水内涝
    ("typhoon_wind", "WeatherHazard"),      # 大风/台风
    ("earthquake", "GeoHazard"),
    ("food_safety", "HealthHazard"),        # 食堂食安
    ("air_quality", "HealthHazard"),        # 教室甲醛/TVOC
    ("illness_cluster", "HealthHazard"),    # 因病缺勤聚集（传染病早期信号）
    ("gate_congestion", "UrbanHazard"),     # 校门口人车混行拥堵
    ("illegal_parking", "UrbanHazard"),
    ("fire_channel_blocked", "UrbanHazard"),
    ("noise", "UrbanHazard"),
    ("asset_damage", "FacilityHazard"),
    ("stair_crowding", "CrowdHazard"),      # 楼梯间人群密度超限（踩踏风险）
]

# T-Box：风险处置知识（hazard → 谓词 → 值）
_HAZARD_KB: dict[str, dict] = {
    "waterlogging": {
        "mitigatedBy": ["启用东门雨棚接送通道", "封闭下凹路段并放置警示桩", "错峰放学改为分班到点呼叫"],
        "responsibleParty": "镇市政维修组 + 交通护学岗·红门管家",
        "notifyLevel": "emergency",
        "recommendPlan": ("rainstorm", "orange"),
    },
    "typhoon_wind": {
        "mitigatedBy": ["加固校门口广告牌/围挡", "停止户外课程", "放学改室内等候点交接"],
        "responsibleParty": "总务处 + 镇应急办",
        "notifyLevel": "emergency",
        "recommendPlan": ("typhoon", "yellow"),
    },
    "earthquake": {
        "mitigatedBy": ["预警倒计时广播·就近伏地掩护", "震动结束后按疏散路线撤离至操场", "清点人数并上报镇应急办"],
        "responsibleParty": "校应急指挥组",
        "notifyLevel": "emergency",
        "recommendPlan": ("earthquake", "warning"),
    },
    "food_safety": {
        "mitigatedBy": ["封存当餐留样送检", "暂停涉事菜品供应", "启动供餐替代方案并公示"],
        "responsibleParty": "食堂负责人 + 区市场监管所",
        "notifyLevel": "important",
        "recommendPlan": None,
    },
    "air_quality": {
        "mitigatedBy": ["涉事教室停用并通风", "班级临时调换至备用教室", "委托CMA机构复测并公示报告"],
        "responsibleParty": "总务处 + 施工方",
        "notifyLevel": "important",
        "recommendPlan": None,
    },
    "gate_congestion": {
        "mitigatedBy": ["启动错峰放学预案", "护学岗增援并打开二号门分流", "引导车辆至错峰共享车位"],
        "responsibleParty": "交通护学岗·红门管家",
        "notifyLevel": "important",
        "recommendPlan": None,
    },
    "illegal_parking": {
        "mitigatedBy": ["现场劝离并推送共享车位导航", "反复违停车辆抄报交警"],
        "responsibleParty": "交通护学岗·红门管家",
        "notifyLevel": "info",
        "recommendPlan": None,
    },
    "fire_channel_blocked": {
        "mitigatedBy": ["立即清障恢复消防通道", "占用主体登记并交镇城管处理"],
        "responsibleParty": "消防安全网格员",
        "notifyLevel": "important",
        "recommendPlan": None,
    },
    "noise": {
        "mitigatedBy": ["定位噪音源并现场核实", "超标施工/商户交镇城管执法队处置"],
        "responsibleParty": "镇城管执法队",
        "notifyLevel": "info",
        "recommendPlan": None,
    },
    "asset_damage": {
        "mitigatedBy": ["生成维修工单", "危及安全的设施先隔离再维修"],
        "responsibleParty": "总务处·后勤维修组",
        "notifyLevel": "info",
        "recommendPlan": None,
    },
    "illness_cluster": {
        "mitigatedBy": ["校医排查同班病例并上报保健科", "加强晨午检与因病缺课登记追踪",
                        "教室通风消毒，必要时错峰活动"],
        "responsibleParty": "校医室 + 班主任",
        "notifyLevel": "important",
        "recommendPlan": None,
    },
    "stair_crowding": {
        "mitigatedBy": ["广播引导分层错时下楼", "楼层值守教师立即到位", "开启备用楼梯分流"],
        "responsibleParty": "楼层值守教师 + 德育处",
        "notifyLevel": "important",
        "recommendPlan": None,
    },
}

# ---------- A-Box：区域个体与属性 ----------

ZONES: dict[str, dict] = {
    "东门": {"type": "GateZone", "floodProne": False, "guardPost": True},
    "东门下凹路段": {"type": "RoadZone", "floodProne": True, "guardPost": False},
    "南门": {"type": "GateZone", "floodProne": False, "guardPost": True},
    "京开辅路口": {"type": "RoadZone", "floodProne": False, "guardPost": True},
    "食堂后厨": {"type": "KitchenZone"},
    "食堂留样间": {"type": "KitchenZone"},
    "六年级教学楼": {"type": "BuildingZone", "renovated": False},
    "六年级教学楼·楼梯间": {"type": "StairZone", "chokePoint": True},
    "翻新教室(六年级1班)": {"type": "ClassroomZone", "renovated": True},
    "六年级1班": {"type": "ClassroomZone"},
    "操场": {"type": "OpenZone", "shelterPoint": True},
    "全校": {"type": "CampusZone"},
}


def superclasses(cls: str) -> list[str]:
    """subClassOf 传递闭包：waterlogging → [WeatherHazard, Hazard]"""
    chain, cur = [], cls
    mapping = dict(_SUBCLASS)
    while cur in mapping:
        cur = mapping[cur]
        chain.append(cur)
    return chain


def hazard_info(hazard_class: str) -> dict:
    kb = _HAZARD_KB.get(hazard_class, {})
    return {
        "class_path": [hazard_class, *superclasses(hazard_class)],
        "mitigated_by": kb.get("mitigatedBy", []),
        "responsible_party": kb.get("responsibleParty", "综合受理台"),
        "notify_level": kb.get("notifyLevel", "info"),
        "recommend_plan": kb.get("recommendPlan"),
    }


# ---------- 规则库：多模态交叉印证 ----------
# signal: {"modality": sensor|vision|citizen|official, "key": 指标/事件/类别/预警类型,
#          "value": 数值(sensor), "level": 预警级别(official), "zone": 区域, "ref": 溯源标识, "at": 时间}

_LEVEL_ORDER = ["blue", "yellow", "orange", "red", "warning"]


def _level_ge(a: str, b: str) -> bool:
    return a in _LEVEL_ORDER and b in _LEVEL_ORDER and _LEVEL_ORDER.index(a) >= _LEVEL_ORDER.index(b)


_FUSION_RULES: list[dict] = [
    {
        "id": "R-WATERLOG",
        "hazard": "waterlogging",
        "patterns": [
            {"modality": "sensor", "key": "water_level_cm", "op": ">=", "value": 15},
            {"modality": "vision", "key": "waterlogging"},
            {"modality": "citizen", "key": "flood"},
            {"modality": "official", "key": "rainstorm", "min_level": "yellow"},
        ],
        "min_modalities": 2,
        "base_severity": 3,
        "escalate": {"modality": "official", "min_level": "orange", "to": 4},
        "default_zone": "东门下凹路段",
    },
    {
        "id": "R-WIND",
        "hazard": "typhoon_wind",
        "patterns": [
            {"modality": "sensor", "key": "wind_ms", "op": ">=", "value": 13.9},  # 7级风
            {"modality": "official", "key": "typhoon", "min_level": "blue"},
            {"modality": "official", "key": "wind", "min_level": "yellow"},
        ],
        "min_modalities": 2,
        "base_severity": 3,
        "escalate": {"modality": "official", "min_level": "orange", "to": 4},
        "default_zone": "全校",
    },
    {
        # 官方地震预警属高可信单源：秒级时效不等待第二模态印证
        "id": "R-QUAKE",
        "hazard": "earthquake",
        "patterns": [{"modality": "official", "key": "earthquake", "min_level": "warning"}],
        "min_modalities": 1,
        "base_severity": 4,
        "default_zone": "全校",
    },
    {
        "id": "R-FOOD",
        "hazard": "food_safety",
        "patterns": [
            {"modality": "sensor", "key": "fridge_temp_c", "op": ">=", "value": 8},  # GB 31654 留样冷藏 0-8℃
            {"modality": "vision", "key": "kitchen_violation"},
            {"modality": "citizen", "key": "food"},
        ],
        "min_modalities": 2,
        "base_severity": 3,
        "default_zone": "食堂后厨",
    },
    {
        "id": "R-AIR",
        "hazard": "air_quality",
        "patterns": [
            {"modality": "sensor", "key": "hcho_mg", "op": ">=", "value": 0.08},  # GB/T 18883 甲醛限值
            {"modality": "sensor", "key": "tvoc_mg", "op": ">=", "value": 0.60},
            {"modality": "citizen", "key": "air"},
        ],
        "min_modalities": 2,
        "base_severity": 3,
        "default_zone": "翻新教室(六年级1班)",
    },
    {
        "id": "R-CONGEST",
        "hazard": "gate_congestion",
        "patterns": [
            {"modality": "vision", "key": "crowd_density"},
            {"modality": "vision", "key": "illegal_parking"},
            {"modality": "citizen", "key": "traffic"},
            {"modality": "sensor", "key": "noise_db", "op": ">=", "value": 70},
        ],
        "min_modalities": 2,
        "base_severity": 2,
        "default_zone": "东门",
    },
    {
        "id": "R-FIRECHAN",
        "hazard": "fire_channel_blocked",
        "patterns": [
            {"modality": "vision", "key": "fire_channel_blocked"},
            {"modality": "citizen", "key": "fire_hazard"},
        ],
        "min_modalities": 2,
        "base_severity": 3,
        "default_zone": "南门",
    },
    {
        # 因病缺勤聚集：请假台账症状聚合（同班3天内同症状≥3例）后产生的聚合信号。
        # 3份独立家长请假单交叉印证等价于多源确认，与地震预警同理走高可信单源直通。
        "id": "R-ILLNESS",
        "hazard": "illness_cluster",
        "patterns": [{"modality": "citizen", "key": "illness_cluster"}],
        "min_modalities": 1,
        "base_severity": 3,
        "default_zone": "六年级1班",
    },
    {
        # 楼梯间拥挤（对标齐齐哈尔体育馆坍塌等聚集事故的"人群聚集踩踏"泛化小类）：
        # 楼梯间边缘相机人群密度 + 噪音计瞬时超限 双模态印证
        "id": "R-STAIR",
        "hazard": "stair_crowding",
        "patterns": [
            {"modality": "vision", "key": "stair_crowding"},
            {"modality": "sensor", "key": "stair_noise_db", "op": ">=", "value": 75},
        ],
        "min_modalities": 2,
        "base_severity": 3,
        "default_zone": "六年级教学楼·楼梯间",
    },
]


def _match(pattern: dict, sig: dict) -> bool:
    if pattern["modality"] != sig.get("modality"):
        return False
    if pattern["key"] != sig.get("key"):
        return False
    if "op" in pattern:
        v = sig.get("value")
        if v is None:
            return False
        return v >= pattern["value"] if pattern["op"] == ">=" else v <= pattern["value"]
    if "min_level" in pattern:
        return _level_ge(str(sig.get("level", "")), pattern["min_level"])
    return True


def fuse(signals: list[dict], now: datetime | None = None) -> list[dict]:
    """前向链推理：signals → 融合风险事件列表（含可解释推理链）"""
    now = now or datetime.utcnow()
    window = now - timedelta(minutes=30)
    fresh = [s for s in signals if s.get("at") is None or s["at"] >= window]

    hazards: list[dict] = []
    for rule in _FUSION_RULES:
        matched: list[tuple[dict, dict]] = []
        for p in rule["patterns"]:
            for s in fresh:
                if _match(p, s):
                    matched.append((p, s))
        modalities = {s["modality"] for _, s in matched}
        if len(modalities) < rule["min_modalities"]:
            continue

        severity = rule["base_severity"]
        esc = rule.get("escalate")
        if esc and any(
            s["modality"] == esc["modality"] and _level_ge(str(s.get("level", "")), esc["min_level"])
            for _, s in matched
        ):
            severity = esc["to"]

        zone = next((s["zone"] for _, s in matched if s.get("zone") in ZONES), rule["default_zone"])
        info = hazard_info(rule["hazard"])

        chain: list[str] = []
        for p, s in matched:
            line = f"信号 [{s['modality']}] {s.get('ref', '?')}: {s['key']}"
            if s.get("value") is not None:
                line += f"={s['value']}"
                if "op" in p:
                    line += f" 触发阈值{p['op']}{p['value']}"
            if s.get("level"):
                line += f" 级别={s['level']}"
            if s.get("zone"):
                line += f" @{s['zone']}"
            chain.append(line)
        chain.append(f"本体: {' ⊑ '.join(info['class_path'])}；区域[{zone}]属性 {ZONES.get(zone, {})}")
        chain.append(
            f"规则 {rule['id']}: {len(modalities)} 类独立模态交叉印证"
            f"（≥{rule['min_modalities']}）→ 确认 {rule['hazard']}，severity={severity}"
        )
        chain.append(f"处置: {info['responsible_party']} → {'；'.join(info['mitigated_by'])}")

        hazards.append({
            "hazard_class": rule["hazard"],
            "zone": zone,
            "severity": severity,
            "sources": [
                {"type": s["modality"], "ref": s.get("ref"), "key": s["key"],
                 "value": s.get("value"), "level": s.get("level")}
                for _, s in matched
            ],
            "inference": "\n".join(chain),
            "suggestion": f"责任方：{info['responsible_party']}。措施：{'；'.join(info['mitigated_by'])}",
            "notify_level": info["notify_level"],
            "recommend_plan": info["recommend_plan"],
        })
    return hazards
