"""资产年检公示 + 场馆点评 API

年检公示墙（7门类，家长可见）：装修甲醛检化验 / 直饮水滤芯 / 消防器材效期 /
教室照明照度(GB 7793) / 体育器械螺栓 / 急救箱药品效期 / 课桌椅身高匹配(GB/T 3976)。
- 效期规则引擎：next_due 超期/临期(30天) 自动标记提醒
- 超龄淘汰建议清单：资产台账 购置年份 × 门类使用年限 → 建议淘汰
- 桌椅身高匹配率：体检身高数据 × 课桌椅型号（两条数据线互相咬合）

场馆点评：教师带队参观后打分评论，后续教师订场地先看口碑，差评规避。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Asset,
    AssetInspection,
    CommunityResource,
    HealthRecord,
    Student,
    User,
    UserRole,
    VenueReview,
)
from ..schemas import InspectionOut, ReviewCreate, ReviewOut

router = APIRouter(tags=["年检公示与场馆点评"])

CATEGORY_LABELS = {
    "renovation": "装修检化验", "water": "直饮水", "fire": "消防器材",
    "lighting": "教室照明", "sports": "体育器械", "medkit": "急救箱",
    "furniture": "课桌椅匹配",
}

# 资产门类 → 建议使用年限（超龄进入淘汰建议清单）
_ASSET_LIFESPAN_YEARS = {"desk": 8, "sports": 6, "renovation": 99}

_DUE_SOON_DAYS = 30


def _due_status(next_due: str | None) -> str:
    if not next_due:
        return "无效期要求"
    today = datetime.now().date()
    due = datetime.strptime(next_due, "%Y-%m-%d").date()
    if due < today:
        return "已超期"
    if due <= today + timedelta(days=_DUE_SOON_DAYS):
        return "临期(30天内)"
    return "在效期内"


# ---------- 年检公示墙 ----------

@router.get("/api/inspections")
def inspection_wall(category: str | None = None, db: Session = Depends(get_db)):
    """年检公示墙：全部检查记录 + 效期状态（家长/全角色可见——公示即监督）"""
    q = db.query(AssetInspection).order_by(AssetInspection.category, AssetInspection.inspect_date.desc())
    if category:
        q = q.filter(AssetInspection.category == category)
    rows = q.all()
    out = []
    for r in rows:
        item = InspectionOut.model_validate(r).model_dump()
        item["category_label"] = CATEGORY_LABELS.get(r.category, r.category)
        item["due_status"] = _due_status(r.next_due)
        out.append(item)
    overdue = [x for x in out if x["due_status"] == "已超期"]
    due_soon = [x for x in out if x["due_status"] == "临期(30天内)"]
    failed = [x for x in out if not x["passed"]]
    return {
        "summary": {"total": len(out), "overdue": len(overdue),
                    "due_soon": len(due_soon), "failed": len(failed),
                    "categories": sorted({x["category"] for x in out})},
        "alerts": [f"【超期】{x['target']}·{x['item']}（应于 {x['next_due']} 前复检）" for x in overdue]
                  + [f"【临期】{x['target']}·{x['item']}（{x['next_due']} 到期）" for x in due_soon]
                  + [f"【不合格】{x['target']}·{x['item']}：{x['result']}" for x in failed],
        "records": out,
    }


@router.get("/api/inspections/retirement-list")
def retirement_list(db: Session = Depends(get_db)):
    """超龄资产淘汰建议清单：购置年份 + 门类年限 + 成色综合判定，一目了然"""
    year_now = datetime.now().year
    rows = db.query(Asset).all()
    out = []
    for a in rows:
        if not a.purchased_year:
            continue
        lifespan = _ASSET_LIFESPAN_YEARS.get(a.category, 10)
        age = year_now - a.purchased_year
        over_age = age >= lifespan
        poor = a.condition <= 2
        if over_age or poor:
            out.append({
                "code": a.code, "name": a.name, "location": a.location,
                "quantity": a.quantity, "purchased_year": a.purchased_year,
                "age_years": age, "lifespan_years": lifespan,
                "condition": a.condition,
                "reason": "、".join(filter(None, [
                    f"已使用{age}年≥建议年限{lifespan}年" if over_age else None,
                    f"成色{a.condition}/5（差）" if poor else None,
                ])),
                "suggestion": "建议列入本年度淘汰更换计划",
            })
    return sorted(out, key=lambda x: (x["condition"], -x["age_years"]))


@router.get("/api/inspections/desk-fit")
def desk_fit(db: Session = Depends(get_db)):
    """课桌椅身高匹配率（GB/T 3976）：体检身高数据 × 现配桌椅型号。
    演示口径：六年级现配3号桌（适配身高143-157cm），按最近一学期体检身高判定。
    """
    fit_range = (143.0, 157.0)
    students = db.query(Student).filter(Student.grade == 6).all()
    matched, mismatched = 0, []
    for s in students:
        latest = (
            db.query(HealthRecord)
            .filter(HealthRecord.student_id == s.id)
            .order_by(HealthRecord.term.desc())
            .first()
        )
        if not latest:
            continue
        if fit_range[0] <= latest.height_cm <= fit_range[1]:
            matched += 1
        else:
            need = "2号桌(150-165cm适用)" if latest.height_cm > fit_range[1] else "4号桌(135-150cm适用)"
            # 隐私：公示只给比例与需调整数量，不公示孩子身高
            mismatched.append({"student_name": s.name[0] + "同学", "suggest": need})
    total = matched + len(mismatched)
    return {
        "basis": "GB/T 3976《学校课桌椅功能尺寸及技术要求》",
        "current_model": "3号桌（适配身高143-157cm）",
        "sampled": total,
        "fit_rate": round(matched / total, 2) if total else None,
        "need_adjust": mismatched,
        "note": "身高数据来自学期体检档案，与健康线互相咬合；仅公示比例，不公示个人身高",
    }


# ---------- 场馆点评 ----------

@router.post("/api/venue-reviews", response_model=ReviewOut, status_code=201)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    resource = db.get(CommunityResource, payload.resource_id)
    if not resource:
        raise HTTPException(404, "场馆资源不存在")
    teacher = db.get(User, payload.teacher_id)
    if not teacher or teacher.role not in (UserRole.teacher, UserRole.admin):
        raise HTTPException(403, "仅带队教师/校长可点评场馆")
    row = VenueReview(
        resource_id=payload.resource_id, teacher_id=teacher.id,
        teacher_name=teacher.name, rating=payload.rating,
        comment=payload.comment, visit_date=payload.visit_date,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/api/venue-reviews/{resource_id}", response_model=list[ReviewOut])
def reviews_of(resource_id: int, db: Session = Depends(get_db)):
    return (
        db.query(VenueReview)
        .filter(VenueReview.resource_id == resource_id)
        .order_by(VenueReview.created_at.desc())
        .all()
    )


@router.get("/api/venue-reputation")
def venue_reputation(db: Session = Depends(get_db)):
    """场馆口碑聚合：均分/条数/最新差评提示——订场地前先看，差评规避"""
    resources = db.query(CommunityResource).all()
    out = []
    for r in resources:
        reviews = db.query(VenueReview).filter(VenueReview.resource_id == r.id).all()
        if not reviews:
            out.append({"resource_id": r.id, "name": r.name, "category": r.category,
                        "avg_rating": None, "review_count": 0, "warning": None})
            continue
        avg = round(sum(v.rating for v in reviews) / len(reviews), 1)
        bad = [v for v in reviews if v.rating <= 2]
        out.append({
            "resource_id": r.id, "name": r.name, "category": r.category,
            "avg_rating": avg, "review_count": len(reviews),
            "warning": f"{bad[-1].teacher_name}：{bad[-1].comment[:50]}" if bad else None,
        })
    return sorted(out, key=lambda x: -(x["avg_rating"] or 0))
