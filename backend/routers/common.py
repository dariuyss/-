from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import LoanApplication


def application_query():
    return select(LoanApplication).options(selectinload(LoanApplication.company), selectinload(LoanApplication.product),
                                           selectinload(LoanApplication.history), selectinload(LoanApplication.documents))


def get_application(db: Session, application_id: int) -> LoanApplication:
    application = db.scalar(application_query().where(LoanApplication.id == application_id))
    if application is None:
        raise HTTPException(404, "Заявка не найдена")
    return application
