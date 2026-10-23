from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CompanyProfile, CreditProduct
from ..schemas import CompanyOut, NewsOut, ProductOut, ProductRecommendation, RecommendRequest
from ..services.external_mocks import company_by_inn, get_or_create_company
from ..services.news_engine import personalized_news

router = APIRouter(prefix="/api", tags=["Каталог и персонализация"])


@router.get("/companies/demo", response_model=list[CompanyOut])
def demo_companies(db: Session = Depends(get_db)):
    return db.scalars(select(CompanyProfile).where(CompanyProfile.is_demo.is_(True)).order_by(CompanyProfile.inn)).all()


@router.get("/companies/{inn}", response_model=CompanyOut)
def company(inn: str, db: Session = Depends(get_db)):
    return get_or_create_company(db, inn)


@router.get("/mocks/company-by-inn/{inn}")
def lookup_company(inn: str):
    return company_by_inn(inn)


@router.get("/products", response_model=list[ProductOut])
def products(db: Session = Depends(get_db)):
    return db.scalars(select(CreditProduct).order_by(CreditProduct.id)).all()


@router.post("/products/recommend", response_model=list[ProductRecommendation])
def recommend(data: RecommendRequest, db: Session = Depends(get_db)):
    purpose = data.purpose.lower()
    result = []
    for p in db.scalars(select(CreditProduct)):
        if not p.min_amount <= data.amount <= p.max_amount or not p.min_term_months <= data.term_months <= p.max_term_months:
            continue
        if p.collateral_required and not data.has_collateral:
            continue
        score = 50
        if p.product_type == "WORKING_CAPITAL":
            score += 30 if any(s in purpose for s in ["товар", "сырь", "оборот", "закуп"]) else 5
        elif p.product_type == "OVERDRAFT":
            score += 40 if any(s in purpose for s in ["разрыв", "кассов", "зарплат"]) else 0
        elif p.product_type == "INVESTMENT":
            score += 40 if any(s in purpose for s in ["оборудован", "ремонт", "расшир", "инвест"]) else 0
        elif p.product_type == "EXPRESS":
            score += 35 if any(s in purpose for s in ["сроч", "быстр", "небольш"]) else 10
        explanation = f"{p.description}. Подходит для суммы {data.amount:,.0f} руб. и срока {data.term_months} мес. "
        explanation += "Потребуется залог." if p.collateral_required else "Залог не требуется."
        result.append(dict(product=p, relevance_score=score, explanation=explanation))
    return sorted(result, key=lambda r: r["relevance_score"], reverse=True)


@router.get("/news/personalized/{inn}", response_model=list[NewsOut])
def news(inn: str, db: Session = Depends(get_db)):
    return personalized_news(db, inn)
