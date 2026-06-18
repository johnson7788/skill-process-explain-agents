import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search.py"
SPEC = importlib.util.spec_from_file_location("searxng_search", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class SearchWithDiagnosticsTests(unittest.TestCase):
    def test_returns_first_success_without_retry(self):
        payload = {
            "results": [
                {
                    "title": "Result 1",
                    "url": "https://example.com/1",
                    "content": "example",
                    "engine": "duckduckgo",
                    "score": 1.0,
                    "category": "general",
                }
            ],
            "number_of_results": 1,
            "answers": [],
            "infoboxes": [],
            "unresponsive_engines": [],
        }

        with patch.object(MODULE.requests, "get", return_value=FakeResponse(payload)) as mock_get:
            results, diagnostics = MODULE.search_with_diagnostics(
                query="医学指南",
                max_attempts=3,
                retry_base_delay=0,
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(len(diagnostics["attempts"]), 1)
        self.assertEqual(diagnostics["final"]["resultsCount"], 1)
        self.assertEqual(mock_get.call_count, 1)

    def test_retries_empty_results_with_unresponsive_engines_until_success(self):
        first_payload = {
            "results": [],
            "number_of_results": 0,
            "answers": [],
            "infoboxes": [],
            "unresponsive_engines": [["duckduckgo", "CAPTCHA"]],
        }
        second_payload = {
            "results": [
                {
                    "title": "Recovered Result",
                    "url": "https://example.com/recovered",
                    "content": "recovered",
                    "engine": "bing",
                    "score": 1.2,
                    "category": "general",
                }
            ],
            "number_of_results": 1,
            "answers": [],
            "infoboxes": [],
            "unresponsive_engines": [],
        }

        with patch.object(
            MODULE.requests,
            "get",
            side_effect=[FakeResponse(first_payload), FakeResponse(second_payload)],
        ) as mock_get, patch.object(MODULE.time, "sleep", return_value=None) as mock_sleep, patch.object(
            MODULE.random,
            "uniform",
            return_value=0,
        ):
            results, diagnostics = MODULE.search_with_diagnostics(
                query="医学指南",
                max_attempts=3,
                retry_base_delay=0.01,
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertEqual(diagnostics["attempts"][0]["retryReason"], "empty_results_with_unresponsive_engines")
        self.assertEqual(diagnostics["final"]["resultsCount"], 1)

    def test_does_not_retry_empty_results_without_unresponsive_engines(self):
        payload = {
            "results": [],
            "number_of_results": 0,
            "answers": [],
            "infoboxes": [],
            "unresponsive_engines": [],
        }

        with patch.object(MODULE.requests, "get", return_value=FakeResponse(payload)) as mock_get, patch.object(
            MODULE.time,
            "sleep",
            return_value=None,
        ) as mock_sleep:
            results, diagnostics = MODULE.search_with_diagnostics(
                query="医学指南",
                max_attempts=3,
                retry_base_delay=0.01,
            )

        self.assertEqual(results, [])
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)
        self.assertEqual(diagnostics["final"]["resultsCount"], 0)

    def test_retries_request_errors_until_attempt_budget_is_exhausted(self):
        error = MODULE.requests.RequestException("network busy")

        with patch.object(MODULE.requests, "get", side_effect=error) as mock_get, patch.object(
            MODULE.time,
            "sleep",
            return_value=None,
        ) as mock_sleep, patch.object(MODULE.random, "uniform", return_value=0):
            with self.assertRaises(MODULE.requests.RequestException):
                MODULE.search_with_diagnostics(
                    query="医学指南",
                    max_attempts=3,
                    retry_base_delay=0.01,
                )

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
