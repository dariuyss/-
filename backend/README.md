# Умный кредитный кабинет предпринимателя

Запускаемый backend хакатон-демо на FastAPI, SQLAlchemy 2.0 и SQLite.
Python 3.11–3.13 (проверено на Python 3.13). Все суммы — рубли, ставки — годовые проценты.

## Запуск

Из корня проекта `хакатон`, в PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs, OpenAPI: http://127.0.0.1:8000/openapi.json.
БД создается автоматически в `backend/credit_cabinet.db`, независимо от рабочего каталога запуска.
Можно задать `DATABASE_URL=sqlite:///C:/absolute/path/demo.db` (родительская папка должна существовать).
При каждом старте идемпотентный seed добавляет отсутствующие продукты, новости, компании и стартовые заявки,
сохраняя текущие статусы, документы и решения. Отдельный запуск: `python -m backend.seed`.
Для демо рекомендуется один процесс Uvicorn; проверки и скоринг выполняются синхронно в одной транзакции.

## Демо для жюри

| ИНН | Компания | Результат скоринга | Статус стартовой заявки |
| --- | --- | --- | --- |
| 7701111111 | ООО «АльфаТех Логистик» | APPROVED | OFFER_GENERATED |
| 7702222222 | ИП Смирнов А.В. «Сеть кофеен Бодрость» | ALTERNATIVE_OFFER | OFFER_GENERATED |
| 7703333333 | ООО «СтройМастер» | MANUAL_REVIEW | NEED_MORE_INFO |
| 7704444444 | ООО «Вектор Торг» | REJECTED | REJECTED |

Сценарий СтройМастера записывает в историю `MANUAL_UNDERWRITING`, затем `NEED_MORE_INFO`.
После загрузки двух запрошенных документов он возвращается в `MANUAL_UNDERWRITING`.
Кофейня получает основной уменьшенный оффер и еще один с меньшей суммой.
`offers[0]` — основной доступный оффер, `offers[1:]` — альтернативы. Изначальная запрошенная сумма
не является одобренным оффером. Поле `reason` объясняет альтернативу.

Любой другой ИНН из 10 или 12 цифр получает синтетический профиль, стабильно вычисляемый по SHA-256 ИНН.
Контрольная сумма не проверяется: заданные ИНН демонстрационные, в том числе 10-значный ИНН ИП.

## API

Все JSON-запросы имеют `Content-Type: application/json`. Ошибки содержат `detail`:
404 — объект не найден; 409 — конфликт статуса/версии; 422 — некорректные данные;
413 — слишком большой документ; 429 — исчерпаны попытки ПЭП; 503 — временная ошибка БД.

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | /api/health | Проверка БД и режима интеграций |
| GET | /api/companies/demo | Четыре демо-компании |
| GET | /api/companies/{inn} | Профиль, создание синтетического при отсутствии |
| GET | /api/mocks/company-by-inn/{inn} | Профиль и снимки ЕГРЮЛ/ЕГРИП, ФНС, БКИ без записи в БД |
| GET | /api/products | Каталог продуктов |
| POST | /api/products/recommend | Подбор по цели, сумме, сроку и залогу |
| GET | /api/news/personalized/{inn} | Лента с personalization_reason |
| POST | /api/applications | Создание и отправка заявки; submit=false сохраняет черновик |
| GET | /api/applications | Список, фильтры inn/status, limit=1..100, offset>=0 |
| GET | /api/applications/{id} | Карточка с историей, документами, снимком проверок и офферами |
| PATCH | /api/applications/{id} | Изменение цели, суммы, срока, залога только в DRAFT |
| POST | /api/applications/{id}/submit | Отправка черновика и полный автоматический конвейер |
| GET | /api/applications/{id}/history | История со статусами, ролями, комментариями, timestamp |
| GET | /api/applications/{id}/offers | Список офферов |
| POST | /api/applications/{id}/select-offer | Выбор по offer_index, индексы с нуля |
| POST | /api/applications/{id}/documents | multipart/form-data: document_type и file |
| GET | /api/applications/{id}/documents/{document_id}/download | Скачать сохраненный файл |
| POST | /api/applications/{id}/sign/request-code | Запрос демо-SMS кода после выбора оффера |
| POST | /api/applications/{id}/sign | Подписание: code и consent=true |
| GET | /api/bank/applications | Очередь, фильтр status, limit/offset |
| GET | /api/bank/applications/{id} | Полное досье |
| POST | /api/bank/applications/{id}/decision | APPROVE / CHANGE_TERMS / REQUEST_DOCUMENTS / REJECT |
| POST | /api/bank/applications/{id}/fund | Демо-выдача после подписания, повторный вызов идемпотентен |

Не найдено подходящих продуктов — подборщик возвращает `[]`, не подменяя желаемые условия.
Для инвестиционного продукта нужен залог. Сроки и суммы проверяются по каталогу.
Досье содержит полный снимок внешних проверок и вход скоринга на момент подачи заявки.
`scoring_result` сохраняет исходное решение stub; актуальное решение банка отражено в `status`, `offers` и `history`.

## Примеры JSON

Подбор продукта (`POST /api/products/recommend`):

```json
{"purpose":"Закупка товаров","amount":1000000,"term_months":12,"has_collateral":false}
```

Новая заявка (`POST /api/applications`):

```json
{
  "inn": "7701111111",
  "product_type": "WORKING_CAPITAL",
  "purpose": "Закупка товаров",
  "requested_amount": 1000000,
  "requested_term_months": 24,
  "has_collateral": false,
  "submit": true
}
```

Выбор оффера (`POST /api/applications/{id}/select-offer`):

```json
{"offer_index":0}
```

Вызовите `POST /api/applications/{id}/sign/request-code` без тела; ответ содержит `demo_code`.
Отправьте этот код в `POST /api/applications/{id}/sign`:

```json
{"code":"123456","consent":true}
```

Код случайный, действует 5 минут, максимум 5 неверных попыток. Новый выбор оффера аннулирует код.
Успешное подписание сохраняет время, хеш подписанных условий и переводит заявку в `ACCEPTED_BY_CLIENT`.
Затем `POST /api/bank/applications/{id}/fund` переводит в `FUNDED` и возвращает `funding_reference`.

Дозапрос (`POST /api/bank/applications/{id}/decision`):

```json
{"decision":"REQUEST_DOCUMENTS","comment":"Нужна выписка за полгода","required_additional_docs":["BANK_STATEMENT_6M"]}
```

Загрузка в PowerShell (поле document_type берется из required_additional_docs):

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/applications/3/documents -F "document_type=BANK_STATEMENT_6M" -F "file=@statement.pdf"
```

Файл сохраняется в SQLite как BLOB, лимит 10 МиБ, пустой файл не принимается.
Незапрошенный тип документа отклоняется. Каждый загруженный документ закрывает один пункт запроса;
при закрытии всех пунктов заявка автоматически возвращается андеррайтеру.
Допускается повторный запрос того же типа документа — потребуется новая загрузка.

Ручное одобрение после получения документов:

```json
{"decision":"APPROVE","comment":"Документы проверены, денежный поток подтвержден"}
```

Изменение условий:

```json
{
  "decision":"CHANGE_TERMS",
  "comment":"Одобрена меньшая сумма",
  "offer": {
    "amount":900000.0,
    "term_months":24,
    "interest_rate":18.0,
    "monthly_payment":1.0,
    "product_type":"WORKING_CAPITAL"
  }
}
```

`monthly_payment` входит в контракт оффера, но банк всегда пересчитывает его на сервере по сумме, сроку и ставке.
Для отказа: `{"decision":"REJECT","comment":"Недостаточный денежный поток"}`.
Решения сотрудника доступны для `MANUAL_UNDERWRITING` и `NEED_MORE_INFO`; одобрение и изменение
условий требуют `MANUAL_UNDERWRITING`, то есть все запрошенные документы должны быть загружены.

## Скоринг и новости

`scoring/schemas.py` сохраняет заданные имена полей, запрещает лишние поля и приведение строк к числам.
Вложенные словари результата валидируются через Factor, Offer и AlternativeOffer.
Для подключения ML замените реализацию `evaluate_application(ScoringInput) -> ScoringResult`.
`current_debt_load` — существующие **ежемесячные платежи** по долгам; DTI = (эти платежи + платеж нового кредита) / месячная чистая прибыль.
При нулевой/отрицательной прибыли stub отказывает; для конечного значения DTI знаменатель ограничен снизу одним рублем.
Аннуитет используется как единый демонстрационный расчет, включая овердрафт.
PD и score — синтетические значения, не обученная модель.

Новости подбираются по префиксу ОКВЭД, самой новой заявке (created_at, затем id), DTI и годовой выручке.
У каждого элемента есть причина персонализации и `is_demo=true`. Материалы синтетические,
не являются актуальной новостной/юридической лентой или подтверждением действующих льгот.

## Проверка

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_api -v
.\.venv\Scripts\python.exe -m pip check
```

Тесты используют отдельную временную SQLite в `backend/tests`, проверяют четыре сценария, транзакционный
откат, черновики, документы, ручные решения, офферы, ПЭП, повторную выдачу, персонализацию, CORS и контракт.
Пользовательская БД не используется. Полный снимок установленных версий — `requirements.lock.txt`.

## Границы демо

API открыт без аутентификации: роли CLIENT, SYSTEM, UNDERWRITER, BANK обозначают источник операций в истории.
ЕГРЮЛ, ФНС, БКИ, SMS, ПЭП и зачисление денег симулируются; реальные сервисы не вызываются.
Для эксплуатации с реальными клиентами потребуются аутентификация и проверка прав, реальные интеграции,
миграции БД, защищенное хранение документов и полноценная реализация подписания.
Автоматическое создание таблиц рассчитано на новую БД и не изменяет схему существующих таблиц.
