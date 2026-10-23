"""Run: python -m unittest backend.scoring.test_train_model"""
import unittest
import numpy as np
import pandas as pd
from .train_model import generate_large_sme_dataset, prepare_features, predict_pd_from_features


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_large_sme_dataset()

    def test_reproducibility_and_population(self):
        pd.testing.assert_frame_equal(self.data, generate_large_sme_dataset())
        self.assertEqual(len(self.data), 2000)
        self.assertEqual(self.data.inn.nunique(), 2000)
        self.assertTrue((self.data.inn.str.len() == np.where(self.data.org_type == "IP", 12, 10)).all())
        self.assertTrue(self.data.default.mean() >= .15)
        self.assertTrue(self.data.default.mean() <= .20)
        self.assertTrue(self.data.annual_revenue.between(1.5e6, 200e6).all())
        self.assertTrue(self.data.requested_amount.between(300e3, 25e6).all())
        self.assertTrue(self.data.business_age_months.between(3, 180).all())
        self.assertTrue(self.data.profit_margin.between(.05 - 1e-12, .25 + 1e-12).all())
        self.assertTrue((~self.data.has_overdue_90_days | self.data.has_overdue_30_days).all())

    def test_feature_contract(self):
        row = self.data.iloc[0].to_dict()
        original = prepare_features(pd.DataFrame([row]))
        row.update(default=999, inn="ignored", dti_ratio=999)
        pd.testing.assert_frame_equal(original, prepare_features(pd.DataFrame([row])))
        row['okved'] = row.pop('okved_code')
        pd.testing.assert_frame_equal(original, prepare_features(pd.DataFrame([row])))
        row['annual_revenue'] = np.inf
        with self.assertRaises(ValueError):
            prepare_features(pd.DataFrame([row]))
        with self.assertRaises(ValueError):
            predict_pd_from_features({})

    def test_saved_model_prediction(self):
        row = self.data.iloc[0].to_dict()
        pd_value = predict_pd_from_features(row)
        self.assertTrue(0 <= pd_value <= 1)
        self.assertEqual(pd_value, predict_pd_from_features(row))
        row['okved_code'] = '99.99'
        self.assertTrue(0 <= predict_pd_from_features(row) <= 1)


if __name__ == '__main__':
    unittest.main()
