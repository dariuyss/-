"""Idempotent seed: independent unique keys; existing customer state is preserved."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CreditProduct, LoanApplication, NewsItem
from .services.external_mocks import PRESETS, get_or_create_company
from .services.workflow import record, submit_application

PRODUCTS = [
    dict(product_type="WORKING_CAPITAL", name="Оборотный кредит", description="Закупка товаров, сырья и оплата текущих расходов", min_amount=100_000., max_amount=50_000_000., min_term_months=3, max_term_months=36, interest_rate=19.5, collateral_required=False),
    dict(product_type="OVERDRAFT", name="Овердрафт", description="Короткий резерв для кассовых разрывов; демо-расчет платежа", min_amount=50_000., max_amount=10_000_000., min_term_months=1, max_term_months=12, interest_rate=21., collateral_required=False),
    dict(product_type="INVESTMENT", name="Инвестиционный", description="Оборудование, ремонт и расширение бизнеса под залог", min_amount=1_000_000., max_amount=100_000_000., min_term_months=12, max_term_months=120, interest_rate=17.5, collateral_required=True),
    dict(product_type="EXPRESS", name="Экспресс-микрокредит", description="Небольшая сумма на срочные задачи бизнеса", min_amount=50_000., max_amount=1_000_000., min_term_months=3, max_term_months=24, interest_rate=24., collateral_required=False),
]

NEWS = [
    dict(key="it", title="IT-бизнес: проверьте доступные меры поддержки", content="Демо-материал: составьте список программ поддержки и уточните условия аккредитации в официальных источниках.", category="INDUSTRY", okved_prefix="62"),
    dict(key="food", title="Общепит: подготовьте процессы учета и маркировки", content="Демо-рекомендация: проверьте категории закупаемых товаров и настройте учет поставок в вашей системе.", category="INDUSTRY", okved_prefix="56"),
    dict(key="construction", title="Строительство: оцените закупки для вашего бизнеса", content="Демо-рекомендация: планируйте обеспечение заявок, сроки оплаты и оборотный капитал перед участием в закупках.", category="INDUSTRY", okved_prefix="41"),
    dict(key="retail", title="Ритейл: управляйте запасами по оборачиваемости", content="Сопоставьте остатки с продажами и выделите быстро оборачиваемые товары для следующей закупки.", category="INDUSTRY", okved_prefix="47"),
    dict(key="offer", title="Предложение готово: сравните платежи с планом продаж", content="Оцените платеж и запас ликвидности. Выберите подходящий оффер и подтвердите договор демо-ПЭП.", category="APPLICATION", target_statuses=["OFFER_GENERATED"]),
    dict(key="funded", title="План использования кредитных средств", content="Разделите бюджет на закупки, операционные расходы и резерв для ежемесячных платежей.", category="APPLICATION", target_statuses=["ACCEPTED_BY_CLIENT", "FUNDED"]),
    dict(key="rejected", title="Как подготовиться к повторной заявке", content="Погасите просрочки и налоговую задолженность, уточните причины блокировки счета, затем оцените меньшую сумму кредита.", category="APPLICATION", target_statuses=["REJECTED"]),
    dict(key="docs", title="Банку нужны дополнительные документы", content="Загрузите запрошенные выписки и отчетность в карточке заявки. После загрузки всех документов заявка вернется андеррайтеру.", category="APPLICATION", target_statuses=["NEED_MORE_INFO"]),
    dict(key="manual", title="Ваша заявка у андеррайтера", content="Специалист проверяет денежный поток и документы. Решение и комментарий появятся в истории заявки.", category="APPLICATION", target_statuses=["MANUAL_UNDERWRITING"]),
    dict(key="dti", title="Снизьте долговую нагрузку перед новым кредитом", content="Составьте график всех платежей, сократите краткосрочный долг и рассмотрите меньшую сумму финансирования.", category="FINANCE", financial_trigger="HIGH_DTI"),
    dict(key="revenue", title="Планирование ликвидности растущей компании", content="При высокой выручке полезно вести платежный календарь на 13 недель и резервировать средства на обязательные платежи.", category="FINANCE", financial_trigger="HIGH_REVENUE"),
    dict(key="general", title="Составьте платежный календарь бизнеса", content="Запишите ожидаемые поступления и расходы на месяц, чтобы заранее видеть кассовые разрывы.", category="EDUCATION"),
]


def seed_database(db: Session):
    for product in PRODUCTS:
        if db.scalar(select(CreditProduct).where(CreditProduct.product_type == product["product_type"])) is None:
            db.add(CreditProduct(**product))
    for news in NEWS:
        if db.scalar(select(NewsItem).where(NewsItem.key == news["key"])) is None:
            db.add(NewsItem(**news))
    db.flush()
    product = db.scalar(select(CreditProduct).where(CreditProduct.product_type == "WORKING_CAPITAL"))
    for inn, amount in zip(PRESETS, [5_000_000., 10_000_000., 3_000_000., 1_000_000.]):
        company = get_or_create_company(db, inn)
        if db.scalar(select(LoanApplication.id).where(LoanApplication.company_id == company.id).limit(1)) is not None:
            continue
        application = LoanApplication(company=company, product=product, purpose="Пополнение оборотных средств (демо)",
                                      requested_amount=amount, requested_term_months=24, status="DRAFT")
        db.add(application)
        record(db, application, "CLIENT", "Создан демонстрационный черновик")
        submit_application(db, application)


if __name__ == "__main__":
    from .database import Base, SessionLocal, engine
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as session:
        seed_database(session)
    print("Demo database seeded")
