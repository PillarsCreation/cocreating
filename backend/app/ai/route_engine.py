"""决策层 · 校园及周边路网图算法

- Dijkstra 疏散路径：危险区域动态加权，实时计算各教学楼到避难点的最优撤离路线
- 儿童友好通学路评分：照明/人行道/护学岗/易涝属性 → 每条通学路线的友好分（呼应"儿童友好城市"命题）
"""
import heapq

# 校园及周边路网：节点 = 本体 Zone 或路网锚点
_NODES: dict[str, dict] = {
    "六年级教学楼": {"kind": "building"},
    "低年级教学楼": {"kind": "building"},
    "食堂": {"kind": "building"},
    "连廊": {"kind": "path", "covered": True},
    "操场": {"kind": "shelter", "capacity": 1600},
    "东门": {"kind": "gate"},
    "南门": {"kind": "gate"},
    "东门下凹路段": {"kind": "road", "flood_prone": True, "lit": False, "sidewalk": False},
    "京开辅路口": {"kind": "road", "lit": True, "sidewalk": True, "guard": True},
    "文体中心": {"kind": "shelter", "capacity": 800},
    "理想城小区": {"kind": "residence"},
    "宏福园小区": {"kind": "residence"},
    "南街高地路线": {"kind": "road", "lit": True, "sidewalk": True, "guard": False},
}

# 无向边：(a, b, 米, 属性)
_EDGES: list[tuple[str, str, float, dict]] = [
    ("六年级教学楼", "连廊", 60, {"covered": True}),
    ("低年级教学楼", "连廊", 40, {"covered": True}),
    ("食堂", "连廊", 50, {"covered": True}),
    ("连廊", "操场", 80, {"covered": False}),
    ("六年级教学楼", "操场", 120, {"covered": False}),
    ("低年级教学楼", "东门", 150, {}),
    ("六年级教学楼", "南门", 130, {}),
    ("操场", "南门", 90, {}),
    ("东门", "东门下凹路段", 100, {}),
    ("东门", "京开辅路口", 220, {}),
    ("东门下凹路段", "理想城小区", 260, {}),
    ("京开辅路口", "理想城小区", 380, {}),
    ("南门", "南街高地路线", 120, {}),
    ("南街高地路线", "宏福园小区", 300, {}),
    ("南街高地路线", "文体中心", 200, {}),
    ("东门下凹路段", "宏福园小区", 420, {}),
]


def _adjacency(blocked: set[str], hazard_zones: dict[str, int]) -> dict[str, list[tuple[str, float]]]:
    """构建邻接表：封闭节点不可通行，风险节点按严重度加权（severity×500m 等效代价）"""
    adj: dict[str, list[tuple[str, float]]] = {n: [] for n in _NODES}
    for a, b, dist, _attrs in _EDGES:
        for u, v in ((a, b), (b, a)):
            if v in blocked:
                continue
            w = dist + hazard_zones.get(v, 0) * 500
            adj[u].append((v, w))
    return adj


def shortest_path(
    start: str,
    goals: set[str],
    blocked: set[str] | None = None,
    hazard_zones: dict[str, int] | None = None,
) -> dict | None:
    """Dijkstra：start → goals 中代价最小的目标。返回 {path, cost_m, goal}"""
    blocked = blocked or set()
    hazard_zones = hazard_zones or {}
    if start not in _NODES or start in blocked:
        return None
    adj = _adjacency(blocked, hazard_zones)

    dist = {start: 0.0}
    prev: dict[str, str] = {}
    pq: list[tuple[float, str]] = [(0.0, start)]
    visited: set[str] = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u in goals:
            path = [u]
            while u in prev:
                u = prev[u]
                path.append(u)
            path.reverse()
            return {"path": path, "cost_m": round(d, 1), "goal": path[-1]}
        for v, w in adj[u]:
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return None


def evacuation_routes(hazard_zones: dict[str, int] | None = None) -> list[dict]:
    """所有教学楼/食堂 → 最优避难点（操场/文体中心）"""
    goals = {n for n, a in _NODES.items() if a.get("kind") == "shelter"}
    starts = [n for n, a in _NODES.items() if a.get("kind") == "building"]
    routes = []
    for s in starts:
        r = shortest_path(s, goals, hazard_zones=hazard_zones)
        if r:
            r["from"] = s
            routes.append(r)
    return routes


# ---------- 儿童友好通学路评分 ----------

_COMMUTE_ROUTES: list[dict] = [
    {"name": "东门→下凹路段→理想城", "nodes": ["东门", "东门下凹路段", "理想城小区"]},
    {"name": "东门→京开辅路口→理想城", "nodes": ["东门", "京开辅路口", "理想城小区"]},
    {"name": "南门→高地路线→宏福园", "nodes": ["南门", "南街高地路线", "宏福园小区"]},
    {"name": "东门→下凹路段→宏福园", "nodes": ["东门", "东门下凹路段", "宏福园小区"]},
]


def child_friendly_scores(hazard_zones: dict[str, int] | None = None) -> list[dict]:
    """通学路线打分（0-100）：照明+25 人行道+25 护学岗+20 无易涝+15 无活跃风险+15"""
    hazard_zones = hazard_zones or {}
    results = []
    for route in _COMMUTE_ROUTES:
        roads = [n for n in route["nodes"] if _NODES.get(n, {}).get("kind") == "road"]
        score, notes = 0, []
        if all(_NODES[r].get("lit") for r in roads):
            score += 25
        else:
            notes.append("存在无照明路段，建议加装路灯")
        if all(_NODES[r].get("sidewalk") for r in roads):
            score += 25
        else:
            notes.append("存在无人行道路段，人车混行")
        if any(_NODES[r].get("guard") for r in roads):
            score += 20
        else:
            notes.append("无护学岗覆盖，建议红门管家增设")
        if not any(_NODES[r].get("flood_prone") for r in roads):
            score += 15
        else:
            notes.append("经过易涝下凹路段，雨天绕行")
        if not any(n in hazard_zones for n in route["nodes"]):
            score += 15
        else:
            notes.append("当前路线上有活跃风险事件")
        results.append({
            "name": route["name"],
            "nodes": route["nodes"],
            "score": score,
            "level": "recommended" if score >= 80 else ("caution" if score >= 50 else "avoid"),
            "notes": notes,
        })
    return sorted(results, key=lambda r: -r["score"])
