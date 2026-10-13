import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.update_data import build_record, extract_major, get_filings, parse_num, validate_api_access, write_csv


class FinancialExtractionTests(unittest.TestCase):
    @patch("src.update_data.api")
    def test_validate_api_access_checks_company_code(self, mocked_api):
        mocked_api.return_value = {"corp_code": "00126380", "corp_name": "삼성전자"}
        company = validate_api_access()
        self.assertEqual(company["corp_code"], "00126380")
        mocked_api.assert_called_once_with("company.json", {"corp_code": "00126380"}, False)

    @patch("src.update_data.api")
    def test_get_filings_continues_when_one_report_category_has_no_data(self, mocked_api):
        mocked_api.side_effect = [
            RuntimeError("DART API list.json: 013 조회된 데이타가 없습니다."),
            {"list": [{"rcept_no": "half"}], "total_page": 1},
            {"list": [{"rcept_no": "quarter"}], "total_page": 1},
        ]
        rows = get_filings(2026)
        self.assertEqual([row["rcept_no"] for row in rows], ["half", "quarter"])
        self.assertEqual(
            [call.args[1]["pblntf_detail_ty"] for call in mocked_api.call_args_list],
            ["A001", "A002", "A003"],
        )

    @patch("src.update_data.api")
    def test_get_filings_filters_official_periodic_report_types(self, mocked_api):
        mocked_api.side_effect = [
            {"list": [{"rcept_no": "annual"}], "total_page": 1},
            {"list": [{"rcept_no": "half"}], "total_page": 1},
            {"list": [{"rcept_no": "quarter"}], "total_page": 1},
        ]
        rows = get_filings(2025)
        self.assertEqual([row["rcept_no"] for row in rows], ["annual", "half", "quarter"])
        self.assertEqual(
            [call.args[1]["pblntf_detail_ty"] for call in mocked_api.call_args_list],
            ["A001", "A002", "A003"],
        )
        for call in mocked_api.call_args_list:
            self.assertEqual(call.args[1]["bgn_de"], "20250101")
            self.assertEqual(call.args[1]["end_de"], "20260430")

    def test_write_csv_accepts_all_ratio_fields(self):
        record = {
            "year": 2025,
            "period": "annual",
            "report_name": "사업보고서",
            "rcept_dt": "20260301",
            "dart_url": "https://dart.fss.or.kr/",
            "major": {"revenue": 1000.0},
            "ratios": {
                "operating_margin": 0.1,
                "net_margin": 0.05,
                "roe": 0.08,
                "roa": 0.04,
                "debt_ratio": 0.5,
                "equity_ratio": 0.6,
                "current_ratio": None,
                "asset_turnover": 0.7,
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            with patch("src.update_data.DATA", Path(folder)):
                write_csv([record])
                csv_file = Path(folder) / "financials.csv"
                self.assertTrue(csv_file.exists())
                header = csv_file.read_text(encoding="utf-8-sig").splitlines()[0]
                self.assertIn("current_ratio", header)

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

    def test_half_year_prefers_cumulative_amount(self):
        rows = [
            {"account_nm": "매출액", "thstrm_amount": "400", "thstrm_add_amount": "900"},
            {"account_nm": "자산총계", "thstrm_amount": "2000", "thstrm_add_amount": ""},
        ]
        values = extract_major(rows, prefer_cumulative=True)
        self.assertEqual(values["revenue"], 900.0)
        self.assertEqual(values["total_assets"], 2000.0)

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
