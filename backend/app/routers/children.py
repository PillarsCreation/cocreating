"""孩子空间 API（家长账号内嵌：一人一档、不一人一号）

学生不设登录账号——家长是唯一监护登录主体。所有读写以 parent_id 校验监护关系：
仅本家长（及班主任/校长）可访问孩子档案。

- 健康档案：多学期身高/体重/视力/口腔纵向对比 + BMI评价 + 视力趋势 + 营养科普建议（守医疗边界）
- 体测档案：国标折算分 + 弱项锻炼处方 + AI视频计数（骨架关键点，不存视频）
- 成绩等级：只做个人纵向对比（优/良/中/待提高），不做班级排名
- 兴趣登记：孩子兴趣标签 + 校外兴趣班（选修课推荐的排除因子）
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..ai import health_engine
from ..database import get_db
from ..models import (
    AcademicRecord,
    ExternalClass,
    FitnessRecord,
    HealthRecord,
    Student,
    User,
    UserRole,
)
from ..schemas import (
    AcademicRecordOut,
    ExternalClassIn,
    ExternalClassOut,
    FitnessRecordOut,
    HealthRecordOut,
    InterestsIn,
    StudentOut,
)

router = APIRouter(prefix="/api/children", tags=["孩子空间"])

_CURRENT_YEAR = 2026


def _guard(db: Session, student_id: int, operator_id: int) -> Student:
    """监护/职务校验：本家长、班主任（同班）、校长可访问"""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "学生档案不存在")
    op = db.get(User, operator_id)
    if not op:
        raise HTTPException(404, "操作人不存在")
    if op.role == UserRole.admin:
        return student
    if op.role == UserRole.teacher and op.class_name == student.class_name:
        return student
    if op.role == UserRole.parent and student.parent_id == op.id:
        return student
    raise HTTPException(403, "仅监护家长、本班班主任或校长可访问孩子档案")


@router.get("/by-parent/{parent_id}", response_model=list[StudentOut])
def children_of_parent(parent_id: int, db: Session = Depends(get_db)):
    parent = db.get(User, parent_id)
    if not parent or parent.role != UserRole.parent:
        raise HTTPException(404, "家长不存在")
    return db.query(Student).filter(Student.parent_id == parent_id).all()


@router.get("/{student_id}/profile")
def child_profile(student_id: int, operator_id: int, db: Session = Depends(get_db)):
    """孩子空间首页聚合：健康纵向对比 + BMI/视力/营养建议 + 体测画像 + 成绩等级"""
    student = _guard(db, student_id, operator_id)

    health_rows = (
        db.query(HealthRecord)
        .filter(HealthRecord.student_id == student_id)
        .order_by(HealthRecord.term)
        .all()
    )
    health = [HealthRecordOut.model_validate(r).model_dump() for r in health_rows]

    bmi = nutrition = None
    if health_rows:
        latest = health_rows[-1]
        age = (_CURRENT_YEAR - student.birth_year) if student.birth_year else 12
        bmi = health_engine.bmi_status(age, student.gender, latest.height_cm, latest.weight_kg)
        nutrition = health_engine.nutrition_advice(bmi, latest.dental_caries)
    vision = health_engine.vision_trend(health)

    fit_rows = (
        db.query(FitnessRecord)
        .filter(FitnessRecord.student_id == student_id)
        .order_by(FitnessRecord.term, FitnessRecord.id)
        .all()
    )
    latest_term = fit_rows[-1].term if fit_rows else None
    latest_fit = [r for r in fit_rows if r.term == latest_term]
    fitness = health_engine.fitness_profile(
        [{"item": r.item, "value": r.value, "score": r.score} for r in latest_fit]
    )
    fitness["records"] = [FitnessRecordOut.model_validate(r).model_dump() for r in fit_rows]

    academic = (
        db.query(AcademicRecord)
        .filter(AcademicRecord.student_id == student_id)
        .order_by(AcademicRecord.term)
        .all()
    )
    external = db.query(ExternalClass).filter(ExternalClass.student_id == student_id).all()

    return {
        "student": StudentOut.model_validate(student).model_dump(),
        "health_records": health,
        "bmi": bmi,
        "vision": vision,
        "nutrition": nutrition,
        "fitness": fitness,
        "academic": [AcademicRecordOut.model_validate(a).model_dump() for a in academic],
        "external_classes": [ExternalClassOut.model_validate(e).model_dump() for e in external],
        "note": "成绩仅做个人纵向对比，不显示班级排名；营养建议为科普提示、非医疗诊断。",
    }


@router.put("/{student_id}/interests", response_model=StudentOut)
def set_interests(student_id: int, payload: InterestsIn, operator_id: int,
                  db: Session = Depends(get_db)):
    """家长代填孩子兴趣标签（选修课推荐因子 F4）"""
    student = _guard(db, student_id, operator_id)
    student.interests = payload.interests
    db.commit()
    db.refresh(student)
    return student


@router.post("/{student_id}/external-classes", response_model=ExternalClassOut, status_code=201)
def add_external_class(student_id: int, payload: ExternalClassIn, operator_id: int,
                       db: Session = Depends(get_db)):
    """登记校外兴趣班：同类选修课自动排除，不重复推荐（推荐因子 F5）"""
    _guard(db, student_id, operator_id)
    row = ExternalClass(student_id=student_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{student_id}/external-classes/{ec_id}")
def remove_external_class(student_id: int, ec_id: int, operator_id: int,
                          db: Session = Depends(get_db)):
    _guard(db, student_id, operator_id)
    row = db.get(ExternalClass, ec_id)
    if not row or row.student_id != student_id:
        raise HTTPException(404, "登记记录不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/{student_id}/fitness-video")
def fitness_video(student_id: int, operator_id: int,
                  item: str = Form(...), term: str = Form(...),
                  video: UploadFile = File(...),
                  db: Session = Depends(get_db)):
    """AI 体测打卡：动作视频 → 骨架关键点计数 + 规范度 + 国标折算分。
    只落库统计结果（source=ai_video），原始视频推理后即丢弃。
    """
    _guard(db, student_id, operator_id)
    if item not in ("一分钟跳绳", "仰卧起坐", "开合跳"):
        raise HTTPException(400, "支持的AI计数项目：一分钟跳绳/仰卧起坐/开合跳")
    content = video.file.read()
    if not content:
        raise HTTPException(400, "视频内容为空")
    result = health_engine.analyze_fitness_video(content, item)

    unit = {"一分钟跳绳": "个/分钟", "仰卧起坐": "个/分钟", "开合跳": "个/分钟"}[item]
    db.add(FitnessRecord(
        student_id=student_id, term=term, item=item,
        value=result["count"], unit=unit,
        score=result["score"] or 0, source="ai_video",
    ))
    db.commit()
    return {**result, "video_discarded": True,
            "message": f"AI计数完成：{result['count']}个，动作规范率{result['form_ok_ratio']:.0%}，已计入体测档案"}
