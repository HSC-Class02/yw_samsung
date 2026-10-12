import unittest

from src.update_data import build_record, extract_major, parse_num


class FinancialExtractionTests(unittest.TestCase):
    def test_parse_num_handles_commas_and_parentheses(self):
        self.assertEqual(parse_num("1,234"), 1234.0)
        self.assertEqual(parse_num("(1,234)"), -1234.0)
        self.assertIsNone(parse_num("-"))

    def test_extract_major_maps_core_account_names(self):
        rows = [
            {"account_nm": "매출액", "thstrm_amount": "1000000"},
            {"account_nm": "영업이익", "thstrm_amount": "100000"},
            {"account_nm": "당기순이익", "thstrm_amount": "80000"},
            {"account_nm": "자산총계", "thstrm_amount": "2000000"},
            {"account_nm": "부채총계", "thstrm_amount": "700000"},
            {"account_nm": "자본총계", "thstrm_amount": "1300000"},
        ]
        major = extract_major(rows)
        self.assertEqual(major["revenue"], 1000000.0)
        self.assertEqual(major["operating_income"], 100000.0)
        self.assertEqual(major["total_assets"], 2000000.0)

    def test_build_record_returns_metric_dictionary_and_ratios(self):
        filing = {
            "reprt_code": "11011",
            "report_nm": "사업보고서 (2025.12)",
            "rcept_no": "20260301000000",
            "rcept_dt": "20260301",
        }
        rows = [
            {"account_nm": "매출액", "thstrm_amount": "1000"},
            {"account_nm": "영업이익", "thstrm_amount": "100"},
            {"account_nm": "당기순이익", "thstrm_amount": "50"},
            {"account_nm": "자산총계", "thstrm_amount": "500"},
            {"account_nm": "부채총계", "thstrm_amount": "200"},
            {"account_nm": "자본총계", "thstrm_amount": "300"},
        ]
        record = build_record(2025, "annual", filing, rows)
        self.assertIsInstance(record["major"], dict)
        self.assertEqual(record["major"]["revenue"], 1000.0)
        self.assertAlmostEqual(record["ratios"]["operating_margin"], 0.1)
        self.assertAlmostEqual(record["ratios"]["roe"], 50.0 / 300.0)


if __name__ == "__main__":
    unittest.main()
