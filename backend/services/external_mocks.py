"""Synthetic data only; no requests to real government or credit bureau services."""
import hashlib
import random
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CompanyProfile

PRESETS = {
    "7701111111": dict(name='ООО «АльфаТех Логистик»', org_type="OOO", okved="62.01", business_age_months=84,
                       annual_revenue=180_000_000., monthly_net_profit=3_000_000., current_debt_load=0.,
                       credit_history_score=950, has_overdue_90_days=False, has_tax_debts=False, fns_blocked=False),
    "7702222222": dict(name='ИП Смирнов А.В. «Сеть кофеен Бодрость»', org_type="IP", okved="56.10", business_age_months=48,
                       annual_revenue=36_000_000., monthly_net_profit=450_000., current_debt_load=80_000.,
                       credit_history_score=790, has_overdue_90_days=False, has_tax_debts=False, fns_blocked=False),
    "7703333333": dict(name='ООО «СтройМастер»', org_type="OOO", okved="41.20", business_age_months=60,
                       annual_revenue=72_000_000., monthly_net_profit=600_000., current_debt_load=260_000.,
                       credit_history_score=610, has_overdue_90_days=False, has_tax_debts=False, fns_blocked=False),
    "7704444444": dict(name='ООО «Вектор Торг»', org_type="OOO", okved="47.11", business_age_months=30,
                       annual_revenue=24_000_000., monthly_net_profit=150_000., current_debt_load=180_000.,
                       credit_history_score=300, has_overdue_90_days=True, has_tax_debts=True, fns_blocked=True),
}


def validate_inn(inn: str) -> str:
    # Checksum intentionally not enforced: jury presets are synthetic, including the 10-digit IP.
    if not re.fullmatch(r"(?:[0-9]{10}|[0-9]{12})", inn):
        raise HTTPException(422, "ИНН должен содержать 10 или 12 цифр")
    return inn


def company_by_inn(inn: str) -> dict:
    validate_inn(inn)
    if inn in PRESETS:
        profile = dict(PRESETS[inn])
    else:
        rng = random.Random(int(hashlib.sha256(inn.encode()).hexdigest(), 16))
        revenue = float(rng.randrange(12, 180) * 1_000_000)
        profile = dict(name=f'{"ИП" if len(inn) == 12 else "ООО"} «Демо-бизнес {inn[-4:]}»',
                       org_type="IP" if len(inn) == 12 else "OOO", okved=rng.choice(["62.01", "56.10", "41.20", "47.11"]),
                       business_age_months=rng.randint(6, 120), annual_revenue=revenue,
                       monthly_net_profit=round(revenue / 12 * rng.uniform(.08, .22), 2),
                       current_debt_load=float(rng.randrange(0, 150) * 1000), credit_history_score=rng.randint(500, 960),
                       has_overdue_90_days=rng.random() < .08, has_tax_debts=rng.random() < .08, fns_blocked=False)
    return {"inn": inn, **profile, "is_demo": inn in PRESETS, "external_data": {
        "is_mock": True,
        "egrul_egrip": {"source": "ЕГРЮЛ/ЕГРИП (симулятор)", "status": "ACTIVE", "name": profile["name"], "okved": profile["okved"]},
        "fns": {"source": "ФНС Прозрачный бизнес (симулятор)", "has_tax_debts": profile["has_tax_debts"], "account_blocked": profile["fns_blocked"]},
        "bki": {"source": "БКИ (симулятор)", "score": profile["credit_history_score"], "has_overdue_90_days": profile["has_overdue_90_days"],
                "monthly_debt_payments": profile["current_debt_load"]},
    }}


def get_or_create_company(db: Session, inn: str) -> CompanyProfile:
    validate_inn(inn)
    company = db.scalar(select(CompanyProfile).where(CompanyProfile.inn == inn))
    if company is None:
        company = CompanyProfile(**company_by_inn(inn))
        db.add(company)
        db.flush()
    return company
