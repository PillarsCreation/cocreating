"""[v4已废弃] 学生成长页路由 —— v4 起学生不设账号（一人一档、不一人一号）。

孩子的健康档案/体测/成绩/兴趣登记迁移至家长账号「孩子空间」：见 routers/children.py。
本文件保留为占位，未在 main.py 注册，无任何路由生效。
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/growth-deprecated", tags=["已废弃"])
