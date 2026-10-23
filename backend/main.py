from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError

from .database import Base, SessionLocal, engine
from .routers import bank, catalog, client
from .seed import seed_database
from .scoring.engine import model_metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_metadata()  # Fail startup clearly if the artifact is absent or incompatible.
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        seed_database(db)
    yield
    engine.dispose()


app = FastAPI(title="Умный кредитный кабинет предпринимателя", version="1.0.0", lifespan=lifespan,
              description="Хакатон-демо: синтетические данные, ML-скоринг на градиентном бустинге, симуляция SMS-ПЭП и выдачи. API без аутентификации.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(catalog.router)
app.include_router(client.router)
app.include_router(bank.router)


@app.exception_handler(StaleDataError)
async def concurrent_update(request: Request, exc: StaleDataError):
    return JSONResponse(status_code=409, content={"detail": "Заявка уже изменена другим запросом. Обновите данные и повторите."})


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Конфликт данных. Обновите данные и повторите запрос."})


@app.exception_handler(OperationalError)
async def database_error(request: Request, exc: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "База данных временно недоступна. Повторите запрос позже."})


@app.get("/api/health", tags=["Сервис"])
def health():
    from sqlalchemy import text
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "scoring_engine": model_metadata()["model_name"],
            "model_version": model_metadata()["model_version"], "external_services": "mocks"}
