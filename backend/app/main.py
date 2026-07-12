"""红门哨兵 · 校园安全与成长智能体（v4）

平急结合、一体两面：
- 急时（安全防范）：暴雨/地震/食安/空气/缺勤聚集/楼梯拥挤 → 感知（IoT+边缘视频）→
  认知（本体多模态融合）→ 决策（预案引擎+图算法）→ 处置（工单+分级分众通知）
- 平时（教联体数字底座）：孩子空间（健康档案/AI体测/成绩纵向）、选修课AI推荐、
  请假台账、用餐日历、资产年检公示、场馆点评——对标教育部等17部门《教联体》方案

账号体系：4角色（校长/班主任/家长/社区）。学生一人一档、不一人一号，
孩子空间内嵌于家长账号。
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import (
    auth,
    brain,
    children,
    courses,
    incidents,
    inspections,
    leave,
    meals,
    misc,
    ops,
    perception,
    resources,
    safety,
    scenario,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="红门哨兵 · 校园安全与成长智能体",
    description="大兴区西红门实验二小 —— 急时安全哨兵，平时教联体数字底座",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(perception.router)
app.include_router(brain.router)
app.include_router(incidents.router)
app.include_router(ops.router)
app.include_router(safety.router)
app.include_router(resources.router)
app.include_router(scenario.router)
app.include_router(misc.router)
app.include_router(children.router)
app.include_router(courses.router)
app.include_router(leave.router)
app.include_router(meals.router)
app.include_router(inspections.router)

_FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
if _FRONTEND.exists():
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(_FRONTEND / "index.html")

    app.mount("/static", StaticFiles(directory=_FRONTEND), name="static")


@app.get("/api/health", tags=["通用"])
def health():
    return {"status": "ok", "service": "redgate-sentinel", "version": "4.0.0"}
