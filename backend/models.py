from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    inn: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str]
    org_type: Mapped[str]
    okved: Mapped[str]
    business_age_months: Mapped[int]
    annual_revenue: Mapped[float]
    monthly_net_profit: Mapped[float]
    current_debt_load: Mapped[float]
    credit_history_score: Mapped[int]
    has_overdue_90_days: Mapped[bool]
    has_tax_debts: Mapped[bool]
    fns_blocked: Mapped[bool] = mapped_column(default=False)
    is_demo: Mapped[bool] = mapped_column(default=False)
    external_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CreditProduct(Base):
    __tablename__ = "credit_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_type: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    min_amount: Mapped[float]
    max_amount: Mapped[float]
    min_term_months: Mapped[int]
    max_term_months: Mapped[int]
    interest_rate: Mapped[float]
    collateral_required: Mapped[bool] = mapped_column(default=False)


class LoanApplication(Base):
    __tablename__ = "loan_applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company_profiles.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("credit_products.id"))
    purpose: Mapped[str]
    requested_amount: Mapped[float]
    requested_term_months: Mapped[int]
    has_collateral: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="DRAFT", index=True)
    scoring_input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scoring_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    external_checks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    offers: Mapped[list] = mapped_column(JSON, default=list)
    selected_offer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    required_additional_docs: Mapped[list] = mapped_column(JSON, default=list)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(nullable=True)
    otp_hash: Mapped[str | None] = mapped_column(nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    otp_attempts: Mapped[int] = mapped_column(default=0)
    funded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    funding_reference: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version}
    company: Mapped[CompanyProfile] = relationship()
    product: Mapped[CreditProduct] = relationship()
    history: Mapped[list["ApplicationHistory"]] = relationship(order_by="ApplicationHistory.id", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(order_by="Document.id", cascade="all, delete-orphan")


class ApplicationHistory(Base):
    __tablename__ = "application_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    status: Mapped[str]
    role: Mapped[str]
    comment: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    document_type: Mapped[str]
    filename: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int]
    sha256: Mapped[str]
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str]
    okved_prefix: Mapped[str | None] = mapped_column(nullable=True)
    target_statuses: Mapped[list] = mapped_column(JSON, default=list)
    financial_trigger: Mapped[str | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
