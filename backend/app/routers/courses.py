"""选修课/课后服务 API：AI个性化推荐（千人千面·可解释）+ 报名闭环

- GET /api/courses?student_id&operator_id：按孩子画像个性化排序，每条带推荐理由；
  personalized=false 关闭个性化（家长可选择原序目录）
- 报名/退课由监护家长操作（学生无账号），报名时快照推荐理由（可解释留痕）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai import course_recommender, health_engine
from ..database import get_db
from ..models import (
    AcademicRecord,
    Course,
    CourseEnrollment,
    ExternalClass,
    FitnessRecord,
    HealthRecord,
    Student,
    User,
    UserRole,
)
from ..schemas import CourseOut, EnrollIn, RecommendedCourse

router = APIRouter(prefix="/api/courses", tags=["选修课"])

_CURRENT_YEAR = 2026


def _build_profile(db: Session, student: Student) -> dict:
    """汇聚推荐六因子输入"""
    fit_rows = (
        db.query(FitnessRecord)
        .filter(FitnessRecord.student_id == student.id)
        .order_by(FitnessRecord.term, FitnessRecord.id)
        .all()
    )
    latest_term = fit_rows[-1].term if fit_rows else None
    latest = [{"item": r.item, "value": r.value, "score": r.score}
              for r in fit_rows if r.term == latest_term]
    fp = health_engine.fitness_profile(latest)

    health_rows = (
        db.query(HealthRecord)
        .filter(HealthRecord.student_id == student.id)
        .order_by(HealthRecord.term)
        .all()
    )
    bmi_status, vision_alert = "正常", False
    if health_rows:
        last = health_rows[-1]
        age = (_CURRENT_YEAR - student.birth_year) if student.birth_year else 12
        bmi_status = health_engine.bmi_status(age, student.gender, last.height_cm, last.weight_kg)["status"]
        vision_alert = health_engine.vision_trend(
            [{"term": r.term, "vision_left": r.vision_left, "vision_right": r.vision_right}
             for r in health_rows]
        )["alert"]

    academic = {}
    for a in db.query(AcademicRecord).filter(AcademicRecord.student_id == student.id).all():
        academic[a.subject] = a.level   # 后写的学期覆盖，留下最新等级

    ext_rows = db.query(ExternalClass).filter(ExternalClass.student_id == student.id).all()
    external = {e.category for e in ext_rows}
    external_names = [e.name for e in ext_rows]
    enrollments = (
        db.query(CourseEnrollment, Course)
        .join(Course, CourseEnrollment.course_id == Course.id)
        .filter(CourseEnrollment.student_id == student.id,
                CourseEnrollment.status == "enrolled")
        .all()
    )
    return {
        "weak_items": fp["weak_items"],
        "strong_items": fp["strong_items"],
        "bmi_status": bmi_status,
        "vision_alert": vision_alert,
        "academic": academic,
        "interests": student.interests or [],
        "external_categories": external,
        "external_names": external_names,
        "enrolled_slots": {(c.weekday, c.time_slot) for _, c in enrollments},
        "enrolled_course_ids": {c.id for _, c in enrollments},
    }


@router.get("", response_model=list[RecommendedCourse])
def list_courses(student_id: int | None = None, operator_id: int | None = None,
                 personalized: bool = True, db: Session = Depends(get_db)):
    courses = [CourseOut.model_validate(c).model_dump()
               for c in db.query(Course).order_by(Course.id).all()]
    if not (personalized and student_id and operator_id):
        return [RecommendedCourse(**c) for c in courses]

    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    op = db.get(User, operator_id)
    if not op or (op.role == UserRole.parent and student.parent_id != op.id):
        raise HTTPException(403, "仅监护家长可查看孩子的个性化推荐")
    ranked = course_recommender.recommend(courses, _build_profile(db, student))
    return [RecommendedCourse(**c) for c in ranked]


@router.post("/{course_id}/enroll", status_code=201)
def enroll(course_id: int, payload: EnrollIn, db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    parent = db.get(User, payload.operator_parent_id)
    if not parent or parent.role not in (UserRole.parent, UserRole.admin) or \
            (parent.role == UserRole.parent and student.parent_id != parent.id):
        raise HTTPException(403, "仅监护家长可为孩子报名")
    if course.enrolled >= course.capacity:
        raise HTTPException(409, "课程名额已满")
    existing = (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.student_id == payload.student_id,
                CourseEnrollment.status == "enrolled")
        .all()
    )
    if any(e.course_id == course_id for e in existing):
        raise HTTPException(409, "已报名本课程")
    for e in existing:
        other = db.get(Course, e.course_id)
        if other and other.weekday == course.weekday and other.time_slot == course.time_slot:
            raise HTTPException(409, f"与已报课程「{other.name}」时段冲突")

    db.add(CourseEnrollment(course_id=course_id, student_id=payload.student_id,
                            reason=payload.reason))
    course.enrolled += 1
    db.commit()
    return {"ok": True, "course": course.name, "enrolled": course.enrolled,
            "reason_snapshot": payload.reason}


@router.post("/{course_id}/cancel")
def cancel(course_id: int, payload: EnrollIn, db: Session = Depends(get_db)):
    student = db.get(Student, payload.student_id)
    parent = db.get(User, payload.operator_parent_id)
    if not student or not parent or \
            (parent.role == UserRole.parent and student.parent_id != parent.id):
        raise HTTPException(403, "仅监护家长可操作")
    row = (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.course_id == course_id,
                CourseEnrollment.student_id == payload.student_id,
                CourseEnrollment.status == "enrolled")
        .first()
    )
    if not row:
        raise HTTPException(404, "未找到有效报名记录")
    row.status = "cancelled"
    course = db.get(Course, course_id)
    if course and course.enrolled > 0:
        course.enrolled -= 1
    db.commit()
    return {"ok": True}


@router.get("/enrollments/{student_id}")
def my_enrollments(student_id: int, operator_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    op = db.get(User, operator_id)
    if not op or (op.role == UserRole.parent and student.parent_id != op.id):
        raise HTTPException(403, "仅监护家长可查看")
    rows = (
        db.query(CourseEnrollment, Course)
        .join(Course, CourseEnrollment.course_id == Course.id)
        .filter(CourseEnrollment.student_id == student_id,
                CourseEnrollment.status == "enrolled")
        .all()
    )
    return [
        {"course_id": c.id, "name": c.name, "category": c.category,
         "weekday": c.weekday, "time_slot": c.time_slot, "teacher": c.teacher,
         "reason_snapshot": e.reason}
        for e, c in rows
    ]
