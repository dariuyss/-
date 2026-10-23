from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scoring.schemas import Offer, ProductType


class Status(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    EXTERNAL_CHECKS = "EXTERNAL_CHECKS"
    SCORING = "SCORING"
    NEED_MORE_INFO = "NEED_MORE_INFO"
    MANUAL_UNDERWRITING = "MANUAL_UNDERWRITING"
    OFFER_GENERATED = "OFFER_GENERATED"
    ACCEPTED_BY_CLIENT = "ACCEPTED_BY_CLIENT"
    FUNDED = "FUNDED"
    REJECTED = "REJECTED"


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", allow_inf_nan=False)


class CompanyOut(APIModel):
    id: int
    inn: str
    name: str
    org_type: str
    okved: str
    business_age_months: int
    annual_revenue: float
    monthly_net_profit: float
    current_debt_load: float
    credit_history_score: int
    has_overdue_90_days: bool
    has_tax_debts: bool
    fns_blocked: bool
    is_demo: bool
    external_data: dict


class ProductOut(APIModel):
    id: int
    product_type: ProductType
    name: str
    description: str
    min_amount: float
    max_amount: float
    min_term_months: int
    max_term_months: int
    interest_rate: float
    collateral_required: bool


class RecommendRequest(APIModel):
    purpose: str = Field(min_length=2, max_length=500)
    amount: float = Field(gt=0, le=1e12)
    term_months: int = Field(ge=1, le=360)
    has_collateral: bool = False


class ProductRecommendation(APIModel):
    product: ProductOut
    relevance_score: int
    explanation: str


class ApplicationCreate(APIModel):
    inn: str = Field(pattern=r"^(?:[0-9]{10}|[0-9]{12})$")
    product_type: ProductType = "WORKING_CAPITAL"
    purpose: str = Field(min_length=2, max_length=500)
    requested_amount: float = Field(gt=0, le=1e12)
    requested_term_months: int = Field(ge=1, le=360)
    has_collateral: bool = False
    submit: bool = True


class ApplicationUpdate(APIModel):
    purpose: str | None = Field(default=None, min_length=2, max_length=500)
    requested_amount: float | None = Field(default=None, gt=0, le=1e12)
    requested_term_months: int | None = Field(default=None, ge=1, le=360)
    has_collateral: bool | None = None

    @model_validator(mode="after")
    def no_explicit_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Поля черновика не могут быть null")
        return self


class HistoryOut(APIModel):
    id: int
    status: Status
    role: str
    comment: str
    timestamp: datetime


class DocumentOut(APIModel):
    id: int
    document_type: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime


class ApplicationOut(APIModel):
    id: int
    company: CompanyOut
    product: ProductOut
    purpose: str
    requested_amount: float
    requested_term_months: int
    has_collateral: bool
    status: Status
    scoring_input: dict | None
    scoring_result: dict | None
    external_checks: dict | None
    offers: list[dict]
    selected_offer: dict | None
    required_additional_docs: list[str]
    rejection_reason: str | None
    signed_at: datetime | None
    funded_at: datetime | None
    funding_reference: str | None
    created_at: datetime
    updated_at: datetime
    version: int
    history: list[HistoryOut]
    documents: list[DocumentOut]


class SelectOffer(APIModel):
    offer_index: int = Field(ge=0)


class SignRequest(APIModel):
    code: str = Field(pattern=r"^[0-9]{6}$")
    consent: Literal[True]


class DecisionRequest(APIModel):
    decision: Literal["APPROVE", "CHANGE_TERMS", "REQUEST_DOCUMENTS", "REJECT"]
    comment: str = Field(min_length=3, max_length=2000)
    offer: Offer | None = None
    required_additional_docs: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_decision(self):
        if self.decision == "CHANGE_TERMS" and self.offer is None:
            raise ValueError("Для изменения условий нужен offer")
        if self.decision == "REQUEST_DOCUMENTS" and (not self.required_additional_docs or
                any(not d.strip() or len(d) > 100 for d in self.required_additional_docs)):
            raise ValueError("Укажите непустые типы запрашиваемых документов (до 100 символов)")
        return self


class NewsOut(APIModel):
    id: int
    title: str
    content: str
    category: str
    published_at: datetime
    personalization_reason: str
    is_demo: bool = True
