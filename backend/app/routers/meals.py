"""用餐日历 API：替代微信群接龙

真实流程还原：饭费不是充卡余额，而是家长在微信群里"填吃饭的日子"接龙得来——
本模块把接龙变成结构化日历：
- 家长按月勾选用餐日，随时可改（当月已过日期不可改）
- 月末按实际勾选天数生成账单，银行卡后付费——全程无饭卡、无余额概念
- 食堂端拿到"次日各班用餐人数"，按人数备餐减少浪费
- 请假批准联动：请假日已勾选用餐 → 提示家长确认取消（系统只建议，不自动动钱）
"""
from datetime import datetime
import calendar

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MealPlan, Student, User, UserRole
from ..schemas import MealPlanOut, MealPlanUpsert

router = APIRouter(prefix="/api/meals", tags=["用餐日历"])


def _guard_parent(db: Session, student_id: int, parent_id: int) -> Student:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    parent = db.get(User, parent_id)
    if not parent or parent.role != UserRole.parent or student.parent_id != parent.id:
        raise HTTPException(403, "仅监护家长可操作孩子的用餐日历")
    return student


@router.put("/plan", response_model=MealPlanOut)
def upsert_plan(payload: MealPlanUpsert, db: Session = Depends(get_db)):
    _guard_parent(db, payload.student_id, payload.parent_id)
    year, month = (int(x) for x in payload.month.split("-"))
    _, last_day = calendar.monthrange(year, month)
    bad = [d for d in payload.days if d < 1 or d > last_day]
    if bad:
        raise HTTPException(400, f"非法日期：{bad}（{payload.month} 只有 {last_day} 天）")
    # 只允许勾选工作日（周末不供餐）
    weekend = [d for d in payload.days
               if datetime(year, month, d).weekday() >= 5]
    if weekend:
        raise HTTPException(400, f"周末不供餐，请去掉：{weekend}日")

    plan = (
        db.query(MealPlan)
        .filter(MealPlan.student_id == payload.student_id,
                MealPlan.month == payload.month)
        .first()
    )
    if plan and plan.billed:
        raise HTTPException(400, "该月账单已生成，不可再修改")
    if plan:
        plan.days = sorted(set(payload.days))
        plan.updated_at = datetime.utcnow()
    else:
        plan = MealPlan(student_id=payload.student_id, month=payload.month,
                        days=sorted(set(payload.days)))
        db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plan/{student_id}/{month}", response_model=MealPlanOut | None)
def get_plan(student_id: int, month: str, operator_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    op = db.get(User, operator_id)
    if not op or (op.role == UserRole.parent and student.parent_id != op.id):
        raise HTTPException(403, "无权查看")
    return (
        db.query(MealPlan)
        .filter(MealPlan.student_id == student_id, MealPlan.month == month)
        .first()
    )


@router.get("/bill/{student_id}/{month}")
def bill_preview(student_id: int, month: str, operator_id: int, db: Session = Depends(get_db)):
    """账单预览：勾选天数 × 单价（月末银行卡后付费，无余额）"""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    op = db.get(User, operator_id)
    if not op or (op.role == UserRole.parent and student.parent_id != op.id):
        raise HTTPException(403, "无权查看")
    plan = (
        db.query(MealPlan)
        .filter(MealPlan.student_id == student_id, MealPlan.month == month)
        .first()
    )
    if not plan:
        return {"month": month, "days_count": 0, "amount": 0,
                "billed": False, "payment": "月末按实际天数银行卡扣款（后付费·无余额）"}
    n = len(plan.days or [])
    return {
        "month": month, "days_count": n, "price_per_meal": plan.price_per_meal,
        "amount": round(n * plan.price_per_meal, 2), "billed": plan.billed,
        "days": plan.days,
        "payment": "月末按实际天数银行卡扣款（后付费·无余额）",
    }


@router.get("/kitchen-forecast")
def kitchen_forecast(date: str | None = None, db: Session = Depends(get_db)):
    """食堂备餐看板：指定日（默认今天）各班用餐人数 → 按人数备餐减少浪费"""
    target = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    month, day = target.strftime("%Y-%m"), target.day
    rows = (
        db.query(MealPlan, Student)
        .join(Student, MealPlan.student_id == Student.id)
        .filter(MealPlan.month == month)
        .all()
    )
    by_class: dict[str, int] = {}
    for plan, student in rows:
        if day in (plan.days or []):
            by_class[student.class_name] = by_class.get(student.class_name, 0) + 1
    total = sum(by_class.values())
    return {
        "date": target.strftime("%Y-%m-%d"),
        "total": total,
        "by_class": [{"class_name": c, "count": n} for c, n in sorted(by_class.items())],
        "note": "按用餐日历实际勾选人数备餐（演示数据仅含六年级1班档案）",
    }


@router.post("/close-month/{month}")
def close_month(month: str, operator_id: int, db: Session = Depends(get_db)):
    """月末结算：锁定该月所有日历并生成账单（演示：批量置 billed）"""
    op = db.get(User, operator_id)
    if not op or op.role != UserRole.admin:
        raise HTTPException(403, "仅校方管理员可执行月末结算")
    plans = db.query(MealPlan).filter(MealPlan.month == month,
                                      MealPlan.billed.is_(False)).all()
    total = 0.0
    for p in plans:
        p.billed = True
        total += len(p.days or []) * p.price_per_meal
    db.commit()
    return {"month": month, "bills_generated": len(plans),
            "total_amount": round(total, 2),
            "note": "账单已生成，家长银行卡后付费扣款（无余额/无饭卡）"}
