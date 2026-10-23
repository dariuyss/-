from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProductType = Literal["WORKING_CAPITAL", "INVESTMENT", "OVERDRAFT", "EXPRESS"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ScoringInput(Contract):
    inn: str = Field(pattern=r"^(?:[0-9]{10}|[0-9]{12})$")
    org_type: Literal["IP", "OOO"]
    okved: str = Field(pattern=r"^[0-9]{2}(?:\.[0-9]{1,2}){0,2}$")
    business_age_months: int = Field(ge=0, le=2400)
    annual_revenue: float = Field(ge=0, le=1e15)
    monthly_net_profit: float = Field(ge=-1e12, le=1e12)
    current_debt_load: float = Field(ge=0, le=1e12)
    credit_history_score: int = Field(ge=0, le=1000)
    has_overdue_90_days: bool
    has_tax_debts: bool
    requested_amount: float = Field(gt=0, le=1e12)
    requested_term_months: int = Field(ge=1, le=360)
    product_type: ProductType


class Factor(Contract):
    factor: str
    impact: int
    description: str


class Offer(Contract):
    amount: float = Field(gt=0, le=1e12)
    term_months: int = Field(ge=1, le=360)
    interest_rate: float = Field(ge=0, le=100)
    monthly_payment: float = Field(gt=0)
    product_type: ProductType


class AlternativeOffer(Offer):
    reason: str = Field(min_length=1)


class ScoringResult(Contract):
    score: int = Field(ge=0, le=1000)
    probability_of_default: float = Field(ge=0, le=1)
    risk_grade: Literal["A", "B", "C", "D"]
    decision: Literal["APPROVED", "ALTERNATIVE_OFFER", "MANUAL_REVIEW", "REJECTED"]
    dti_ratio: float = Field(ge=0)
    factors_explanation: list[dict]
    recommended_offer: dict | None
    alternative_offers: list[dict]
    required_additional_docs: list[str]

    @field_validator("factors_explanation")
    @classmethod
    def validate_factors(cls, values):
        return [Factor.model_validate(v).model_dump() for v in values]

    @field_validator("recommended_offer")
    @classmethod
    def validate_offer(cls, value):
        return None if value is None else Offer.model_validate(value).model_dump()

    @field_validator("alternative_offers")
    @classmethod
    def validate_alternatives(cls, values):
        return [AlternativeOffer.model_validate(v).model_dump() for v in values]
