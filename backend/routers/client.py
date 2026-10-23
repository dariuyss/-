import hashlib
import hmac
import json
import secrets
from datetime import timedelta, timezone
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CreditProduct, Document, LoanApplication, utcnow
from ..schemas import (ApplicationCreate, ApplicationOut, ApplicationUpdate, DocumentOut,
                       HistoryOut, SelectOffer, SignRequest, Status)
from ..services.external_mocks import get_or_create_company, validate_inn
from ..services.workflow import record, require_status, submit_application, transition, validate_product
from .common import application_query, get_application

router = APIRouter(prefix="/api/applications", tags=["Клиент — заявки"])
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(data: ApplicationCreate, db: Session = Depends(get_db)):
    company = get_or_create_company(db, data.inn)
    product = db.scalar(select(CreditProduct).where(CreditProduct.product_type == data.product_type))
    if product is None:
        raise HTTPException(404, "Продукт не найден")
    application = LoanApplication(company=company, product=product, purpose=data.purpose,
                                  requested_amount=data.requested_amount, requested_term_months=data.requested_term_months,
                                  has_collateral=data.has_collateral, status="DRAFT")
    if data.financial_overrides is not None:
        application.scoring_input = {"financial_overrides": data.financial_overrides.model_dump()}
    validate_product(application)
    db.add(application)
    record(db, application, "CLIENT", "Создан черновик заявки")
    if data.submit:
        submit_application(db, application)
    return application


@router.get("", response_model=list[ApplicationOut])
def list_applications(inn: str | None = None, status: Status | None = None,
                      limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = application_query()
    if inn:
        validate_inn(inn)
        from ..models import CompanyProfile
        query = query.join(LoanApplication.company).where(CompanyProfile.inn == inn)
    if status:
        query = query.where(LoanApplication.status == status.value)
    return db.scalars(query.order_by(LoanApplication.id.desc()).offset(offset).limit(limit)).all()


@router.get("/{application_id}", response_model=ApplicationOut)
def detail(application_id: int, db: Session = Depends(get_db)):
    return get_application(db, application_id)


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_draft(application_id: int, data: ApplicationUpdate, db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    require_status(application, "DRAFT")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    validate_product(application)
    record(db, application, "CLIENT", "Обновлены условия черновика")
    return application


@router.post("/{application_id}/submit", response_model=ApplicationOut)
def submit(application_id: int, db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    submit_application(db, application)
    return application


@router.get("/{application_id}/history", response_model=list[HistoryOut])
def history(application_id: int, db: Session = Depends(get_db)):
    return get_application(db, application_id).history


@router.get("/{application_id}/offers", response_model=list[dict])
def offers(application_id: int, db: Session = Depends(get_db)):
    return get_application(db, application_id).offers


@router.post("/{application_id}/select-offer", response_model=ApplicationOut)
def select_offer(application_id: int, data: SelectOffer, db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    require_status(application, "OFFER_GENERATED")
    if data.offer_index >= len(application.offers):
        raise HTTPException(422, "Оффер с таким индексом отсутствует")
    application.selected_offer = dict(application.offers[data.offer_index])
    application.otp_hash = None
    application.otp_expires_at = None
    record(db, application, "CLIENT", f"Выбран оффер {data.offer_index}; ожидается подписание ПЭП")
    return application


@router.post("/{application_id}/documents", response_model=DocumentOut, status_code=201)
def upload_document(application_id: int, document_type: str = Form(..., min_length=1, max_length=100),
                    file: UploadFile = File(...), db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    require_status(application, "NEED_MORE_INFO")
    if document_type not in application.required_additional_docs:
        raise HTTPException(422, "Такой документ не запрошен")
    content = file.file.read(MAX_DOCUMENT_BYTES + 1)
    if not content:
        raise HTTPException(422, "Файл пустой")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(413, "Максимальный размер файла — 10 МБ")
    filename = PurePosixPath((file.filename or "document").replace("\\", "/")).name[:255]
    document = Document(document_type=document_type, filename=filename, content_type=file.content_type or "application/octet-stream",
                        content=content, size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    application.documents.append(document)
    application.required_additional_docs = [d for d in application.required_additional_docs if d != document_type]
    record(db, application, "CLIENT", f"Загружен документ {document_type}: {filename}")
    if not application.required_additional_docs:
        transition(db, application, "MANUAL_UNDERWRITING", "SYSTEM", "Все запрошенные документы загружены; заявка возвращена андеррайтеру")
    return document


@router.get("/{application_id}/documents/{document_id}/download")
def download_document(application_id: int, document_id: int, db: Session = Depends(get_db)):
    get_application(db, application_id)
    document = db.get(Document, document_id)
    if document is None or document.application_id != application_id:
        raise HTTPException(404, "Документ не найден")
    from urllib.parse import quote
    return Response(content=document.content, media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}",
                             "X-Content-Type-Options": "nosniff"})


@router.post("/{application_id}/sign/request-code")
def request_code(application_id: int, db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    require_status(application, "OFFER_GENERATED")
    if application.selected_offer is None:
        raise HTTPException(409, "Сначала выберите оффер")
    code = f"{secrets.randbelow(1_000_000):06d}"
    application.otp_hash = hashlib.sha256(f"{application.id}:{code}".encode()).hexdigest()
    application.otp_expires_at = utcnow() + timedelta(minutes=5)
    application.otp_attempts = 0
    record(db, application, "SYSTEM", "Создан одноразовый код демо-ПЭП со сроком 5 минут")
    return {"demo_code": code, "expires_in_seconds": 300, "message": "Симуляция SMS: используйте demo_code для подписания"}


@router.post("/{application_id}/sign", response_model=ApplicationOut)
def sign(application_id: int, data: SignRequest, db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    require_status(application, "OFFER_GENERATED")
    expires = application.otp_expires_at
    if expires is None or expires.replace(tzinfo=timezone.utc) < utcnow() or not application.otp_hash:
        raise HTTPException(409, "Запросите действующий код ПЭП")
    if application.otp_attempts >= 5:
        raise HTTPException(429, "Попытки исчерпаны; запросите новый код")
    digest = hashlib.sha256(f"{application.id}:{data.code}".encode()).hexdigest()
    if not hmac.compare_digest(digest, application.otp_hash):
        application.otp_attempts += 1
        record(db, application, "CLIENT", "Неверный код демо-ПЭП")
        # Persist failed attempts despite the HTTP error; do not commit other business operations here.
        db.commit()
        raise HTTPException(422, "Неверный код ПЭП")
    if application.selected_offer is None:
        raise HTTPException(409, "Оффер не выбран")
    application.signed_at = utcnow()
    payload = json.dumps({"application_id": application.id, "offer": application.selected_offer,
                          "signed_at": application.signed_at.isoformat(), "consent": True}, sort_keys=True)
    application.signature_hash = hashlib.sha256(payload.encode()).hexdigest()
    application.otp_hash = None
    application.otp_expires_at = None
    transition(db, application, "ACCEPTED_BY_CLIENT", "CLIENT", "Выбранные условия подписаны демо-ПЭП; согласие подтверждено")
    return application
