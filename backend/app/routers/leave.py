"""请假台账 API：家长发起 → 班主任审批 → 自动落账

真实痛点：请假散落在微信聊天里，班主任说不清每个孩子每月/每学期请了几天假。
本模块把请假变成结构化台账：
- 班级统计：每生每月/学期请假天数一目了然（无AI也有管理价值，如实呈现）
- 因病缺勤聚集预警：病假症状标签聚合——同班3天内同症状≥3例 → citizen 模态信号
  进入本体融合（R-ILLNESS），提示校医与班主任（因病缺课登记追踪是国家强制要求，
  现实中多为手工登记，这里补上数字化闭环）
- 请假日与用餐日历联动：批准整天假时返回"建议取消当日用餐"提示，家长确认后自行
  修改用餐日历——系统不自动动钱
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import LeaveRequest, MealPlan, Student, User, UserRole
from ..schemas import LeaveApprove, LeaveCreate, LeaveOut
from ..services.fusion import run_fusion

router = APIRouter(prefix="/api/leave", tags=["请假台账"])

CLUSTER_WINDOW_DAYS = 3
CLUSTER_THRESHOLD = 3   # 同班同症状 ≥3例 → 聚集预警


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _weekdays_between(start: date, end: date) -> float:
    """请假天数按工作日计（周末不上学不计入）"""
    n, cur = 0, start
    while cur <= end:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return float(n)


@router.post("", response_model=LeaveOut, status_code=201)
def create_leave(payload: LeaveCreate, db: Session = Depends(get_db)):
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    parent = db.get(User, payload.parent_id)
    if not parent or parent.role != UserRole.parent or student.parent_id != parent.id:
        raise HTTPException(403, "仅监护家长可为孩子请假")
    start, end = _parse(payload.start_date), _parse(payload.end_date)
    if end < start:
        raise HTTPException(400, "结束日期不能早于开始日期")
    if payload.leave_type == "sick" and not payload.symptoms:
        raise HTTPException(400, "病假请勾选症状标签（用于校园健康监测，也便于班主任了解情况）")

    row = LeaveRequest(
        student_id=payload.student_id,
        start_date=payload.start_date, end_date=payload.end_date,
        days=_weekdays_between(start, end),
        leave_type=payload.leave_type, symptoms=payload.symptoms,
        note=payload.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/by-student/{student_id}", response_model=list[LeaveOut])
def leaves_of_student(student_id: int, operator_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    op = db.get(User, operator_id)
    if not op or (op.role == UserRole.parent and student.parent_id != op.id):
        raise HTTPException(403, "无权查看")
    return (
        db.query(LeaveRequest)
        .filter(LeaveRequest.student_id == student_id)
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )


@router.get("/pending")
def pending_leaves(operator_id: int, db: Session = Depends(get_db)):
    """班主任待审批列表（本班）；校长看全校"""
    op = db.get(User, operator_id)
    if not op or op.role not in (UserRole.teacher, UserRole.admin):
        raise HTTPException(403, "仅班主任/校长可审批请假")
    q = (
        db.query(LeaveRequest, Student)
        .join(Student, LeaveRequest.student_id == Student.id)
        .filter(LeaveRequest.status == "pending")
    )
    if op.role == UserRole.teacher:
        q = q.filter(Student.class_name == op.class_name)
    return [
        {**LeaveOut.model_validate(r).model_dump(),
         "student_name": s.name, "class_name": s.class_name}
        for r, s in q.order_by(LeaveRequest.created_at).all()
    ]


@router.post("/{leave_id}/approve")
def approve_leave(leave_id: int, payload: LeaveApprove, db: Session = Depends(get_db)):
    row = db.get(LeaveRequest, leave_id)
    if not row:
        raise HTTPException(404, "请假单不存在")
    if row.status != "pending":
        raise HTTPException(400, "该请假单已处理")
    student = db.get(Student, row.student_id)
    op = db.get(User, payload.operator_id)
    if not op or op.role not in (UserRole.teacher, UserRole.admin):
        raise HTTPException(403, "仅班主任/校长可审批")
    if op.role == UserRole.teacher and op.class_name != student.class_name:
        raise HTTPException(403, "只能审批本班学生的请假")

    row.status = "approved" if payload.approve else "rejected"
    row.approved_by = op.name
    db.commit()

    # 病假批准后触发一轮融合：症状聚合信号进入本体（R-ILLNESS 缺勤聚集预警）
    cluster = None
    if payload.approve and row.leave_type == "sick":
        run_fusion(db)
        cluster = illness_watch_for_class(db, student.class_name)

    # 请假日 × 用餐日历重叠 → 仅建议，家长确认后自行修改（不自动动钱）
    meal_suggestion = None
    if payload.approve:
        overlaps = _meal_overlap(db, row)
        if overlaps:
            meal_suggestion = {
                "message": f"{student.name} 请假日中有 {len(overlaps)} 天已勾选在校用餐，"
                           "已提示家长确认是否取消当日用餐（系统不自动扣退费用）",
                "dates": overlaps,
            }

    return {"ok": True, "status": row.status, "approved_by": row.approved_by,
            "illness_cluster": cluster, "meal_suggestion": meal_suggestion}


def _meal_overlap(db: Session, leave: LeaveRequest) -> list[str]:
    start, end = _parse(leave.start_date), _parse(leave.end_date)
    overlaps: list[str] = []
    cur = start
    while cur <= end:
        plan = (
            db.query(MealPlan)
            .filter(MealPlan.student_id == leave.student_id,
                    MealPlan.month == cur.strftime("%Y-%m"))
            .first()
        )
        if plan and cur.day in (plan.days or []):
            overlaps.append(cur.isoformat())
        cur += timedelta(days=1)
    return overlaps


@router.get("/class-stats")
def class_stats(class_name: str, operator_id: int, db: Session = Depends(get_db)):
    """班级请假统计：每生累计天数（月/学期）——班主任首次能答上"孩子这学期请了几天假" """
    op = db.get(User, operator_id)
    if not op or op.role not in (UserRole.teacher, UserRole.admin):
        raise HTTPException(403, "仅班主任/校长可查看班级统计")
    if op.role == UserRole.teacher and op.class_name != class_name:
        raise HTTPException(403, "只能查看本班统计")

    students = db.query(Student).filter(Student.class_name == class_name).all()
    this_month = datetime.now().strftime("%Y-%m")
    out = []
    for s in students:
        rows = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.student_id == s.id, LeaveRequest.status == "approved")
            .all()
        )
        month_days = sum(r.days for r in rows if r.start_date.startswith(this_month))
        term_days = sum(r.days for r in rows)
        sick = sum(r.days for r in rows if r.leave_type == "sick")
        out.append({"student_id": s.id, "student_name": s.name,
                    "month_days": month_days, "term_days": term_days,
                    "sick_days": sick, "personal_days": term_days - sick})
    return {"class_name": class_name, "month": this_month,
            "stats": sorted(out, key=lambda x: -x["term_days"])}


def illness_watch_for_class(db: Session, class_name: str) -> list[dict]:
    """近3天同班同症状病假聚合（供审批后即时反馈与融合信号源共用）"""
    since = (datetime.now() - timedelta(days=CLUSTER_WINDOW_DAYS)).strftime("%Y-%m-%d")
    rows = (
        db.query(LeaveRequest, Student)
        .join(Student, LeaveRequest.student_id == Student.id)
        .filter(Student.class_name == class_name,
                LeaveRequest.leave_type == "sick",
                LeaveRequest.status == "approved",
                LeaveRequest.start_date >= since)
        .all()
    )
    counter: dict[str, list[str]] = {}
    for r, s in rows:
        for sym in (r.symptoms or []):
            counter.setdefault(sym, []).append(s.name)
    return [
        {"symptom": sym, "cases": len(names), "students": names,
         "alert": len(names) >= CLUSTER_THRESHOLD,
         "action": "已达聚集阈值：提示校医排查、加强晨午检与教室通风消毒" if len(names) >= CLUSTER_THRESHOLD else None}
        for sym, names in sorted(counter.items(), key=lambda kv: -len(kv[1]))
    ]


@router.get("/illness-watch")
def illness_watch(operator_id: int, db: Session = Depends(get_db)):
    """全校因病缺勤聚集看板（校长/班主任）：按班×症状聚合近3天病假"""
    op = db.get(User, operator_id)
    if not op or op.role not in (UserRole.teacher, UserRole.admin):
        raise HTTPException(403, "仅班主任/校长可查看")
    classes = [c[0] for c in db.query(Student.class_name).distinct().all()]
    if op.role == UserRole.teacher:
        classes = [c for c in classes if c == op.class_name]
    return {
        "window_days": CLUSTER_WINDOW_DAYS, "threshold": CLUSTER_THRESHOLD,
        "classes": [
            {"class_name": c, "symptoms": illness_watch_for_class(db, c)}
            for c in classes
        ],
    }
