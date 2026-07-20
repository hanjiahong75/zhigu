"""User profile service: investment preferences and context building."""

from sqlalchemy.orm import Session
from ..models.database import SessionLocal
from ..models.stock import UserProfile


def get_or_create_profile(db: Session, user_id: int = 1) -> UserProfile:
    """Get existing profile or create default for user_id."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(
    db: Session,
    user_id: int = 1,
    investment_style: str | None = None,
    risk_preference: str | None = None,
    focus_industries: str | None = None,
    focus_stocks: str | None = None,
) -> UserProfile:
    """Update user profile fields."""
    profile = get_or_create_profile(db, user_id)
    if investment_style is not None:
        profile.investment_style = investment_style
    if risk_preference is not None:
        profile.risk_preference = risk_preference
    if focus_industries is not None:
        profile.focus_industries = focus_industries
    if focus_stocks is not None:
        profile.focus_stocks = focus_stocks
    db.commit()
    db.refresh(profile)
    return profile


def build_profile_context(db: Session, user_id: int = 1) -> str:
    """Build a user-profile context string for system prompt injection (R10 appropriateness)."""
    if db is None:
        return ""
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    except Exception:
        return ""

    if not profile:
        return ""

    parts = []
    style_map = {"short_term": "短线交易", "medium_term": "中线波段", "long_term": "长线价值投资"}
    risk_map = {"conservative": "保守型（低风险偏好）", "moderate": "稳健型（中等风险偏好）", "aggressive": "积极型（高风险偏好）"}

    style_label = style_map.get(profile.investment_style, profile.investment_style)
    risk_label = risk_map.get(profile.risk_preference, profile.risk_preference)

    parts.append(f"## 用户画像")
    parts.append(f"- 投资风格：{style_label}")
    parts.append(f"- 风险偏好：{risk_label}")

    if profile.focus_industries:
        parts.append(f"- 关注行业：{profile.focus_industries}")
    if profile.focus_stocks:
        parts.append(f"- 重点关注股票：{profile.focus_stocks}")

    parts.append("请结合以上用户画像，在分析时优先关注用户偏好的行业和风格，给出更贴合用户需求的分析角度。")
    return "\n".join(parts)
