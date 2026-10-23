"""Reproducible synthetic SME scoring demo, not a validated bank PD model.

Run from the repository root: python backend/scoring/train_model.py
All artifacts are written beside this module. No network or external data needed.
"""
from functools import lru_cache
from pathlib import Path
import json
import platform

import sklearn

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (brier_score_loss, confusion_matrix, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42
DIRECTORY = Path(__file__).resolve().parent
MODEL_PATH = DIRECTORY / "trained_scoring_model.pkl"
CATEGORICAL = ["org_type", "okved_code"]
BOOLEAN = ["has_overdue_30_days", "has_overdue_90_days", "has_tax_debts",
           "has_fns_account_blockings"]
NUMERIC = ["business_age_months", "annual_revenue", "monthly_net_profit",
           "current_debt_load", "requested_amount", "credit_history_score",
           "tax_payments_to_revenue_ratio"]
DERIVED = ["dti_ratio", "loan_to_revenue_ratio", "profit_margin"]
FEATURES = CATEGORICAL + NUMERIC + BOOLEAN + DERIVED


def prepare_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Shared training/inference contract; ignore identifiers and supplied ratios."""
    data = frame.copy()
    if "okved_code" not in data and "okved" in data:
        data["okved_code"] = data["okved"]
    missing = set(CATEGORICAL + NUMERIC + BOOLEAN) - set(data.columns)
    if missing:
        raise ValueError(f"Missing required scoring features: {sorted(missing)}")
    data["org_type"] = data["org_type"].replace({"ИП": "IP", "ООО": "OOO"})
    if not data["org_type"].isin(["IP", "OOO"]).all():
        raise ValueError("org_type must be IP/OOO or ИП/ООО")
    if not data["okved_code"].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
        raise ValueError("okved_code must be a nonempty string")
    for column in NUMERIC:
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not np.isfinite(data[column]).all():
            raise ValueError(f"{column} must be finite")
        if column != "monthly_net_profit" and (data[column] < 0).any():
            raise ValueError(f"{column} must be nonnegative")
    for column in BOOLEAN:
        if not data[column].map(lambda v: isinstance(v, (bool, np.bool_, int, np.integer)) and v in (0, 1)).all():
            raise ValueError(f"{column} must be a boolean or 0/1")
        data[column] = data[column].astype(int)
    data["dti_ratio"] = data.current_debt_load / data.monthly_net_profit.clip(lower=1.0)
    data["loan_to_revenue_ratio"] = data.requested_amount / data.annual_revenue.clip(lower=1.0)
    data["profit_margin"] = data.monthly_net_profit * 12 / data.annual_revenue.clip(lower=1.0)
    if not np.isfinite(data[NUMERIC + DERIVED].to_numpy()).all():
        raise ValueError("Financial ratios must be finite")
    return data[FEATURES]


def _synthetic_inn(index: int, individual: bool) -> str:
    # Prefix 00 keeps the identifiers explicitly synthetic; checksum is valid.
    digits = [int(c) for c in "00" + str(index + 1).zfill(8 if individual else 7)]
    weights = ([7, 2, 4, 10, 3, 5, 9, 4, 6, 8] if individual
               else [2, 4, 10, 3, 5, 9, 4, 6, 8])
    digits.append(sum(d * w for d, w in zip(digits, weights)) % 11 % 10)
    if individual:
        weights = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        digits.append(sum(d * w for d, w in zip(digits, weights)) % 11 % 10)
    return "".join(map(str, digits))


def generate_large_sme_dataset(n_samples: int = 2000, random_state: int = RANDOM_STATE) -> pd.DataFrame:
    """Generate synthetic applications and noisy simulated 12-month outcomes.

    6% symmetric label-flip noise is applied after Bernoulli sampling. The
    intercept targets 17.5% expected defaults, accounting for those flips.
    Realized prevalence fluctuates naturally; labels are never edited to hit it.
    """
    if isinstance(n_samples, bool) or not isinstance(n_samples, int) or not 1 <= n_samples <= 9_999_999:
        raise ValueError("n_samples must be an integer between 1 and 9,999,999")
    rng = np.random.default_rng(random_state)
    org = rng.choice(["IP", "OOO"], n_samples, p=[.4, .6])
    sector = rng.choice(["62.01", "56.10", "47.11", "41.20", "49.41"], n_samples,
                        p=[.18, .20, .30, .17, .15])
    # Economic relationships are scenario assumptions, not fitted Russian statistics.
    revenue = np.clip(rng.lognormal(np.log(18e6), 1.05, n_samples)
                      * np.where(org == "IP", .7, 1.2), 1.5e6, 200e6)
    margin = np.clip(rng.uniform(.05, .23, n_samples)
                     + np.where(sector == "62.01", .02, 0), .05, .25)
    profit = revenue * margin / 12
    debt = profit * np.clip(rng.gamma(1.5, .22, n_samples), 0, 2)
    debt[rng.random(n_samples) < .25] = 0
    overdue90 = rng.random(n_samples) < .05
    overdue30 = overdue90 | (rng.random(n_samples) < (.15 - .05) / .95)
    data = pd.DataFrame({
        "inn": [_synthetic_inn(i, o == "IP") for i, o in enumerate(org)],
        "org_type": org, "okved_code": sector,
        "business_age_months": rng.integers(3, 181, n_samples),
        "annual_revenue": revenue, "monthly_net_profit": profit,
        "current_debt_load": debt,
        "requested_amount": np.clip(revenue * rng.lognormal(np.log(.2), .7, n_samples), 300e3, 25e6),
        "credit_history_score": np.clip(rng.normal(680, 95, n_samples), 300, 850).round().astype(int),
        "has_overdue_30_days": overdue30, "has_overdue_90_days": overdue90,
        "has_tax_debts": rng.random(n_samples) < .10,
        "has_fns_account_blockings": rng.random(n_samples) < .04,
        "tax_payments_to_revenue_ratio": np.clip(rng.normal(.05, .012, n_samples), .005, .10),
    })
    features = prepare_features(data)
    data[DERIVED] = features[DERIVED]
    risk = (3.8 * (data.dti_ratio > .6) + .6 * data.dti_ratio
            + 4.5 * data.has_overdue_90_days + 4.2 * data.has_fns_account_blockings
            + 3.5 * (data.credit_history_score < 500)
            + 3.2 * (data.business_age_months < 6)
            + .8 * data.has_overdue_30_days + 1.0 * data.has_tax_debts
            + .8 * data.loan_to_revenue_ratio.clip(upper=3)
            + .5 * (data.tax_payments_to_revenue_ratio < .03)
            + .6 * (650 - data.credit_history_score) / 100
            - 2 * data.profit_margin).to_numpy()
    noise = .06
    low, high = -30.0, 30.0
    for _ in range(80):
        intercept = (low + high) / 2
        probabilities = 1 / (1 + np.exp(-np.clip(risk + intercept, -40, 40)))
        if (noise + (1 - 2 * noise) * probabilities).mean() < .175:
            low = intercept
        else:
            high = intercept
    labels = rng.random(n_samples) < probabilities
    labels ^= rng.random(n_samples) < noise
    data["default"] = labels.astype(int)
    return data


def train_model() -> dict:
    data = generate_large_sme_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        prepare_features(data), data["default"], test_size=.2,
        random_state=RANDOM_STATE, stratify=data["default"])
    # Selected gradient boosting configuration; all calibration stays inside training data.
    base_pipeline = Pipeline([
        ("preprocessing", ColumnTransformer([
            ("numeric", StandardScaler(), NUMERIC + BOOLEAN + DERIVED),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ])),
        ("classifier", HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=3,
            learning_rate=.05, l2_regularization=5, min_samples_leaf=30,
            early_stopping=False, random_state=RANDOM_STATE)),
    ])
    pipeline = CalibratedClassifierCV(base_pipeline, method="sigmoid",
        cv=StratifiedKFold(3, shuffle=True, random_state=RANDOM_STATE), n_jobs=1)
    pipeline.fit(X_train, y_train)
    pd_test = pipeline.predict_proba(X_test)[:, 1]
    predictions = (pd_test >= .5).astype(int)
    report = {
        "data_source": "synthetic_demo_only", "model": "hist_boosting_sigmoid",
        "random_state": RANDOM_STATE,
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "scikit_learn": sklearn.__version__,
                     "joblib": joblib.__version__},
        "n_samples": len(data), "train_samples": len(y_train), "test_samples": len(y_test),
        "default_rate": float(data.default.mean()), "threshold": .5,
        "roc_auc": float(roc_auc_score(y_test, pd_test)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "brier_score": float(brier_score_loss(y_test, pd_test)),
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=[0, 1]).tolist(),
    }
    # Save exactly the evaluated model; test rows are never included in training.
    joblib.dump(pipeline, MODEL_PATH)
    _load_model.cache_clear()
    data.to_csv(DIRECTORY / "synthetic_sme_dataset.csv", index=False)
    (DIRECTORY / "scoring_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Model saved: {MODEL_PATH}")
    print("Synthetic holdout only: these metrics do not establish real-world PD accuracy.")
    return report


@lru_cache(maxsize=1)
def _load_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Model missing: {MODEL_PATH}. Run python backend/scoring/train_model.py first.")
    # Load only your own trusted artifact: joblib/pickle can execute code.
    return joblib.load(MODEL_PATH)


def predict_pd_from_features(company_features: dict) -> float:
    """Predict a synthetic PD; required fields are NUMERIC, BOOLEAN, CATEGORICAL.

    Accepts `okved` as an alias. Missing fields fail explicitly. Extra API fields
    and INN are ignored. Restart API workers after replacing the model artifact.
    """
    features = prepare_features(pd.DataFrame([company_features]))
    model = _load_model()
    positive = list(model.classes_).index(1)
    return float(model.predict_proba(features)[0, positive])


if __name__ == "__main__":
    train_model()
