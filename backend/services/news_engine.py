from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import LoanApplication, NewsItem
from .external_mocks import get_or_create_company

SECTORS = {"62": "IT", "56": "Общепит", "41": "Строительство", "47": "Ритейл"}


def personalized_news(db: Session, inn: str) -> list[dict]:
    company = get_or_create_company(db, inn)
    application = db.scalar(select(LoanApplication).where(LoanApplication.company_id == company.id)
                            .order_by(LoanApplication.created_at.desc(), LoanApplication.id.desc()).limit(1))
    status = application.status if application else None
    dti = (application.scoring_result or {}).get("dti_ratio", 0) if application else 0
    debt_ratio = company.current_debt_load / max(company.monthly_net_profit, 1)
    feed = []
    for item in db.scalars(select(NewsItem).order_by(NewsItem.published_at.desc(), NewsItem.id)):
        reasons = []
        if item.okved_prefix:
            if not company.okved.startswith(item.okved_prefix):
                continue
            reasons.append(f"Подобрано для ОКВЭД {company.okved} ({SECTORS.get(item.okved_prefix, 'Бизнес')})")
        if item.target_statuses:
            if status not in item.target_statuses:
                continue
            reasons.append(f"На основе статуса вашей заявки: {status}")
        if item.financial_trigger == "HIGH_DTI":
            if max(dti, debt_ratio) <= .5:
                continue
            reasons.append(f"Долговая нагрузка превышает 50% месячной прибыли (DTI {max(dti, debt_ratio):.2f})")
        if item.financial_trigger == "HIGH_REVENUE":
            if company.annual_revenue < 100_000_000:
                continue
            reasons.append("Годовая выручка вашего бизнеса от 100 млн руб.")
        feed.append(dict(id=item.id, title=item.title, content=item.content, category=item.category,
                         published_at=item.published_at, personalization_reason="; ".join(reasons) or "Рекомендация для всех предпринимателей", is_demo=True))
    return sorted(feed, key=lambda n: n["personalization_reason"] == "Рекомендация для всех предпринимателей")
