"""End-to-end checks on isolated, file-backed SQLite; no live integrations."""
import os
from pathlib import Path
import tempfile
import unittest

TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="credit-tests-", dir=Path(__file__).parent)
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(TEST_DIRECTORY.name) / "test.db").as_posix()

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from backend.database import SessionLocal, engine
from backend.main import app
from backend.models import LoanApplication
from backend.scoring.schemas import ScoringInput, ScoringResult
from backend.seed import seed_database


class CreditFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        engine.dispose()
        TEST_DIRECTORY.cleanup()

    def create(self, inn="7701111111", **overrides):
        payload = dict(inn=inn, product_type="WORKING_CAPITAL", purpose="Закупка товаров",
                       requested_amount=1_000_000, requested_term_months=24, has_collateral=False)
        payload.update(overrides)
        response = self.client.post("/api/applications", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_seed_scenarios_and_idempotence(self):
        with SessionLocal.begin() as db:
            count = db.scalar(select(func.count()).select_from(LoanApplication))
            seed_database(db)
            self.assertEqual(count, db.scalar(select(func.count()).select_from(LoanApplication)))
        expected = {"7701111111": ("APPROVED", "OFFER_GENERATED"),
                    "7702222222": ("ALTERNATIVE_OFFER", "OFFER_GENERATED"),
                    "7703333333": ("MANUAL_REVIEW", "NEED_MORE_INFO"),
                    "7704444444": ("REJECTED", "REJECTED")}
        for inn, (decision, status) in expected.items():
            applications = self.client.get("/api/applications", params={"inn": inn}).json()
            seed = min(applications, key=lambda a: a["id"])
            self.assertEqual(seed["scoring_result"]["decision"], decision)
            self.assertEqual(seed["status"], status)
            ScoringResult.model_validate(seed["scoring_result"])

    def test_approved_sign_and_funding(self):
        a = self.create()
        base = f'/api/applications/{a["id"]}'
        self.assertEqual(self.client.post(base + "/sign/request-code").status_code, 409)
        self.assertEqual(self.client.post(f'/api/bank/applications/{a["id"]}/fund').status_code, 409)
        response = self.client.post(base + "/select-offer", json={"offer_index": 0})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "OFFER_GENERATED")
        code = self.client.post(base + "/sign/request-code").json()["demo_code"]
        signed = self.client.post(base + "/sign", json={"code": code, "consent": True})
        self.assertEqual(signed.status_code, 200, signed.text)
        self.assertEqual(signed.json()["status"], "ACCEPTED_BY_CLIENT")
        funded = self.client.post(f'/api/bank/applications/{a["id"]}/fund')
        self.assertEqual(funded.json()["status"], "FUNDED")
        retry = self.client.post(f'/api/bank/applications/{a["id"]}/fund').json()
        self.assertEqual(retry["funding_reference"], funded.json()["funding_reference"])
        self.assertEqual(len(retry["history"]), len(funded.json()["history"]))
        self.assertEqual(self.client.post(base + "/sign", json={"code": code, "consent": True}).status_code, 409)
        self.assertNotIn("otp_hash", funded.json())
        with SessionLocal() as db:
            persisted = db.get(LoanApplication, a["id"])
            self.assertEqual(persisted.status, "FUNDED")
            self.assertIsNotNone(persisted.signature_hash)

    def test_manual_documents_decision(self):
        a = self.create("7703333333")
        base = f'/api/applications/{a["id"]}'
        bank = f'/api/bank/applications/{a["id"]}/decision'
        self.assertEqual(self.client.post(bank, json={"decision": "APPROVE", "comment": "Проверено"}).status_code, 409)
        for doc_type in a["required_additional_docs"]:
            response = self.client.post(base + "/documents", data={"document_type": doc_type},
                                        files={"file": ("report.txt", b"synthetic report", "text/plain")})
            self.assertEqual(response.status_code, 201, response.text)
            doc_id = response.json()["id"]
            self.assertEqual(self.client.get(base + f"/documents/{doc_id}/download").content, b"synthetic report")
        a = self.client.get(base).json()
        self.assertEqual(a["status"], "MANUAL_UNDERWRITING")
        requested = self.client.post(bank, json={"decision": "REQUEST_DOCUMENTS", "comment": "Нужен контракт", "required_additional_docs": ["CONTRACT"]})
        self.assertEqual(requested.json()["status"], "NEED_MORE_INFO")
        self.client.post(base + "/documents", data={"document_type": "CONTRACT"}, files={"file": ("c.txt", b"contract")})
        changed = self.client.post(bank, json={"decision": "CHANGE_TERMS", "comment": "Подтвержден денежный поток",
            "offer": {"amount": 900_000., "term_months": 24, "interest_rate": 18., "monthly_payment": 1., "product_type": "WORKING_CAPITAL"}})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()["status"], "OFFER_GENERATED")
        self.assertGreater(changed.json()["offers"][0]["monthly_payment"], 1)
        states = [h["status"] for h in changed.json()["history"]]
        self.assertIn("MANUAL_UNDERWRITING", states)
        self.assertIn("NEED_MORE_INFO", states)

    def test_alternative_offer_and_rejection(self):
        a = self.create("7702222222", requested_amount=10_000_000)
        self.assertEqual(a["scoring_result"]["decision"], "ALTERNATIVE_OFFER")
        self.assertGreaterEqual(len(a["offers"]), 2)
        self.assertLess(a["offers"][0]["amount"], a["requested_amount"])
        selected = self.client.post(f'/api/applications/{a["id"]}/select-offer', json={"offer_index": 1}).json()
        self.assertEqual(selected["selected_offer"], a["offers"][1])
        rejected = self.create("7704444444")
        self.assertEqual(rejected["status"], "REJECTED")
        self.assertIn("90+", rejected["rejection_reason"])
        self.assertEqual(self.client.post(f'/api/applications/{rejected["id"]}/select-offer', json={"offer_index": 0}).status_code, 409)

    def test_draft_and_transaction_rollback(self):
        a = self.create(submit=False)
        base = f'/api/applications/{a["id"]}'
        self.assertEqual(a["status"], "DRAFT")
        self.assertEqual(self.client.patch(base, json={"requested_amount": 1}).status_code, 422)
        self.assertEqual(self.client.get(base).json()["requested_amount"], a["requested_amount"])
        self.assertEqual(self.client.patch(base, json={"requested_amount": None}).status_code, 422)
        self.assertEqual(self.client.patch(base, json={"requested_amount": 500_000}).status_code, 200)
        submitted = self.client.post(base + "/submit")
        self.assertEqual(submitted.json()["status"], "OFFER_GENERATED")
        self.assertEqual(self.client.post(base + "/submit").status_code, 409)
        self.assertEqual(self.client.patch(base, json={"purpose": "Новая цель"}).status_code, 409)

    def test_otp_attempt_limit(self):
        a = self.create()
        base = f'/api/applications/{a["id"]}'
        self.client.post(base + "/select-offer", json={"offer_index": 0})
        code = self.client.post(base + "/sign/request-code").json()["demo_code"]
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.client.post(base + "/sign", json={"code": wrong, "consent": True}).status_code, 422)
        self.assertEqual(self.client.post(base + "/sign", json={"code": code, "consent": True}).status_code, 429)
        code = self.client.post(base + "/sign/request-code").json()["demo_code"]
        self.assertEqual(self.client.post(base + "/sign", json={"code": code, "consent": True}).status_code, 200)

    def test_manual_rejection_and_invalid_document(self):
        a = self.create("7703333333")
        base = f'/api/applications/{a["id"]}'
        response = self.client.post(base + "/documents", data={"document_type": "NOT_REQUESTED"}, files={"file": ("x", b"test")})
        self.assertEqual(response.status_code, 422)
        response = self.client.post(base + "/documents", data={"document_type": a["required_additional_docs"][0]}, files={"file": ("empty", b"")})
        self.assertEqual(response.status_code, 422)
        response = self.client.post(f'/api/bank/applications/{a["id"]}/decision', json={"decision": "REJECT", "comment": "Недостаточный денежный поток"})
        self.assertEqual(response.json()["status"], "REJECTED")
        self.assertEqual(response.json()["rejection_reason"], "Недостаточный денежный поток")

    def test_news_recommendations_and_mocks(self):
        for inn, prefix in [("7701111111", "62.01"), ("7702222222", "56.10"), ("7703333333", "41.20"), ("7704444444", "47.11")]:
            news = self.client.get(f"/api/news/personalized/{inn}").json()
            self.assertTrue(any(prefix in n["personalization_reason"] for n in news))
            self.assertTrue(all(n["personalization_reason"] for n in news))
        self.create("7704444444")
        news = self.client.get("/api/news/personalized/7704444444").json()
        self.assertTrue(any("REJECTED" in n["personalization_reason"] for n in news))
        first = self.client.get("/api/mocks/company-by-inn/7812345678").json()
        self.assertEqual(first, self.client.get("/api/mocks/company-by-inn/7812345678").json())
        self.assertEqual(self.client.get("/api/mocks/company-by-inn/bad").status_code, 422)
        r = self.client.post("/api/products/recommend", json={"purpose": "Закупка оборудования", "amount": 5_000_000, "term_months": 60, "has_collateral": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()[0]["product"]["product_type"], "INVESTMENT")
        self.assertEqual(self.client.post("/api/products/recommend", json={"purpose": "Оборудование", "amount": 5_000_000, "term_months": 60, "has_collateral": False}).json(), [])

    def test_strict_contract_and_openapi(self):
        a = self.create()
        payload = a["scoring_input"]
        payload["requested_term_months"] = "24"
        with self.assertRaises(ValidationError):
            ScoringInput.model_validate(payload)
        result = a["scoring_result"]
        result["recommended_offer"]["amount"] = -1
        with self.assertRaises(ValidationError):
            ScoringResult.model_validate(result)
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")
        cors = self.client.options("/api/products", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
        self.assertEqual(cors.headers["access-control-allow-origin"], "*")

    def test_client_financials_reach_scoring_without_changing_mocks(self):
        original = self.client.get('/api/mocks/company-by-inn/7701111111').json()
        figures = {"annual_revenue": 12_000_000, "monthly_net_profit": 100_000, "current_debt_load": 80_000}
        a = self.create(financial_overrides=figures)
        self.assertEqual(a['scoring_input']['monthly_net_profit'], 100_000)
        self.assertEqual(a['scoring_input']['annual_revenue'], 12_000_000)
        self.assertNotEqual(a['scoring_result']['decision'], 'APPROVED')
        self.assertEqual(a['external_checks']['client_declared_financials'], figures)
        self.assertEqual(a['external_checks']['monthly_net_profit'], original['monthly_net_profit'])
        self.assertEqual(self.client.get('/api/mocks/company-by-inn/7701111111').json(), original)
        draft = self.create(submit=False, financial_overrides=figures)
        submitted = self.client.post(f'/api/applications/{draft["id"]}/submit').json()
        self.assertEqual(submitted['scoring_input']['monthly_net_profit'], 100_000)


if __name__ == "__main__":
    unittest.main()
