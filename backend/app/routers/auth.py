"""登录认证 API（演示版）

黑客松演示用的轻量认证：预置4个角色账号，密码明文比对。
生产环境应替换为 JWT + 密码哈希（bcrypt）。

管理员定位：依据《中小学校岗位安全工作指南》，校长是学校安全工作第一责任人，
故 admin 账号即校长（日常值守可授权安全干部/总务处，本演示合并为一个账号）。

学生不设账号（一人一档、不一人一号）：小学生无手机、低年级无自主操作能力，
未成年人数据最小化原则下监护人是唯一合法操作主体——孩子的健康档案/选课/请假
全部内嵌在家长账号的「孩子空间」中。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 演示账号：用户名 → (密码, 种子用户姓名, 附加信息)
# 演示主线人物锚定在六年级1班：翻新教室甲醛监测、六年级课桌成色最差均发生在该班
DEMO_ACCOUNTS: dict[str, dict] = {
    "teacher": {"password": "123456", "user_name": "李老师",
                "extra": {"manage_class": "六年级1班"}},
    "parent": {"password": "123456", "user_name": "王女士",
               "extra": {"child_name": "小明", "child_class": "六年级1班"}},
    "community": {"password": "123456", "user_name": "张主任",
                  "extra": {"org": "理想城社区居委会·红门管家",
                            "duty": "共享空间审批 + 工单处置"}},
    "admin": {"password": "123456", "user_name": "赵校长",
              "extra": {"duty": "学校安全工作第一责任人"}},
}


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user_id: int
    name: str
    role: str
    extra: dict


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    account = DEMO_ACCOUNTS.get(payload.username)
    if not account or account["password"] != payload.password:
        raise HTTPException(401, "用户名或密码错误")
    user = db.query(User).filter(User.name == account["user_name"]).first()
    if not user:
        raise HTTPException(500, "种子用户缺失，请先运行 seed.py")
    return LoginResponse(
        user_id=user.id, name=user.name, role=user.role.value, extra=account["extra"]
    )


@router.get("/accounts")
def demo_accounts():
    """返回演示身份列表（登录页点选身份即进入，不下发密码）"""
    role_labels = {"teacher": "六年级1班班主任",
                   "parent": "六年级1班家长（内嵌孩子空间）",
                   "community": "社区居委会·红门管家",
                   "admin": "校长·安全第一责任人"}
    return [
        {"username": u, "name": a["user_name"],
         "role": u, "role_label": role_labels[u]}
        for u, a in DEMO_ACCOUNTS.items()
    ]
