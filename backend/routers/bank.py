import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import LoanApplication, utcnow
from ..schemas import ApplicationOut, DecisionRequest, Status
from ..services.workflow import bank_decision, require_status, transition
from .common import application_query, get_application

router = APIRouter(prefix="/api/bank/applications", tags=["Банк — конвейер"])


@router.get("", response_model=list[ApplicationOut])
def applications(status: Status | None = None, limit: int = Query(50, ge=1, le=100),
                 offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = application_query()
    if status:
        query = query.where(LoanApplication.status == status.value)
    return db.scalars(query.order_by(LoanApplication.id.desc()).offset(offset).limit(limit)).all()


@router.get("/{application_id}", response_model=ApplicationOut)
def dossier(application_id: int, db: Session = Depends(get_db)):
    return get_application(db, application_id)


@router.post("/{application_id}/decision", response_model=ApplicationOut)
def decide(application_id: int, data: DecisionRequest, db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    bank_decision(db, application, data)
    return application


@router.post("/{application_id}/fund", response_model=ApplicationOut)
def fund(application_id: int, db: Session = Depends(get_db)):
    application = get_application(db, application_id)
    if application.status == "FUNDED":
        return application  # Idempotent retry does not issue funds twice.
    require_status(application, "ACCEPTED_BY_CLIENT")
    application.funded_at = utcnow()
    application.funding_reference = f"DEMO-{uuid.uuid4().hex}"
    transition(db, application, "FUNDED", "BANK", f"Демо-зачисление на расчетный счет; операция {application.funding_reference}")
    return application
