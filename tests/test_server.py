import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
    urlopen,
)

from src.server import create_server


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(port=0, host="127.0.0.1")
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)

    def test_root_serves_url_form_and_collision_visualizer(self):
        with urlopen(f"{self.base_url}/") as response:
            page = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertIn("text/html", response.headers["Content-Type"])
        self.assertIn('id="shorten-form"', page)
        self.assertIn('id="visualize-form"', page)
        self.assertIn('postJson("/shorten"', page)
        self.assertIn('postJson("/visualize"', page)
        self.assertIn("https://example.com/a", page)
        self.assertIn("https://example.com/i", page)
        self.assertIn('id="collision-resolution"', page)
        self.assertIn('value="linear_probing"', page)
        self.assertIn("slot_probes", page)

    def test_table_page_shows_bucket_and_slot_states_and_hash_rule(self):
        with urlopen(f"{self.base_url}/table") as response:
            empty_page = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertIn("Horner", empty_page)
        self.assertIn("h = (h * 31 + ord(character)) % capacity", empty_page)
        self.assertIn("Bucket 7", empty_page)
        self.assertIn("Slot 7", empty_page)
        self.assertIn("empty", empty_page)

        self._post_json("/shorten", {"url": "https://example.com/a"})
        self._post_json("/shorten", {"url": "https://example.com/i"})
        with urlopen(f"{self.base_url}/table") as response:
            populated_page = response.read().decode("utf-8")

        self.assertIn("https://example.com/a", populated_page)
        self.assertIn("https://example.com/i", populated_page)
        self.assertIn("chain", populated_page.lower())
        self.assertIn("probe", populated_page.lower())
        self.assertIn("slot 0", populated_page.lower())
        self.assertIn("slot 1", populated_page.lower())

    def test_shorten_returns_code_and_duplicate_status_with_forwarded_origin(self):
        url = "https://example.com/a"
        request_headers = {
            "X-Forwarded-Host": "my-codespace-8000.app.github.dev",
            "X-Forwarded-Proto": "https",
        }

        first_status, first_body = self._post_json(
            "/shorten",
            {"url": url},
            request_headers,
        )
        duplicate_status, duplicate_body = self._post_json(
            "/shorten",
            {"url": url},
            request_headers,
        )

        self.assertEqual(first_status, 201)
        self.assertEqual(duplicate_status, 200)
        self.assertEqual(first_body["code"], "1")
        self.assertEqual(duplicate_body["code"], first_body["code"])
        self.assertEqual(
            first_body["short_url"],
            f"https://my-codespace-8000.app.github.dev/{first_body['code']}",
        )

    def test_invalid_json_and_invalid_urls_return_bad_request(self):
        status, _body = self._post_raw("/shorten", b"{not-json")
        self.assertEqual(status, 400)

        for payload in (
            {},
            {"url": ""},
            {"url": "ftp://example.com/resource"},
            {"url": "https:///missing-host"},
            {"url": 17},
        ):
            with self.subTest(payload=payload):
                status, _body = self._post_json("/shorten", payload)
                self.assertEqual(status, 400)

    def test_short_code_redirects_to_original_url_without_following_it(self):
        original_url = "https://example.com/resource"
        _status, body = self._post_json("/shorten", {"url": original_url})
        request = Request(f"{self.base_url}/{body['code']}")
        opener = build_opener(NoRedirectHandler())

        with self.assertRaises(HTTPError) as raised:
            opener.open(request, timeout=2)

        self.assertEqual(raised.exception.code, 302)
        self.assertEqual(raised.exception.headers["Location"], original_url)

    def test_unknown_short_code_returns_not_found(self):
        with self.assertRaises(HTTPError) as raised:
            urlopen(f"{self.base_url}/unknown", timeout=2)

        self.assertEqual(raised.exception.code, 404)

    def test_visualizer_shows_horner_steps_chain_and_comparison_process(self):
        first_url = "https://example.com/a"
        second_url = "https://example.com/i"
        self._post_json("/shorten", {"url": first_url})
        _status, second_short = self._post_json(
            "/shorten",
            {"url": second_url},
        )

        status, trace = self._post_json("/visualize", {"key": second_url})

        self.assertEqual(status, 200)
        self.assertEqual(trace["key"], second_url)
        self.assertGreaterEqual(trace["bucket_index"], 0)
        self.assertLess(trace["bucket_index"], 8)
        self.assertTrue(trace["collision"])
        self.assertTrue(trace["found"])
        self.assertEqual(trace["value"], second_short["code"])
        self.assertEqual(trace["comparisons"], 2)
        self.assertEqual(
            [entry["key"] for entry in trace["chain"]],
            [first_url, second_url],
        )
        self.assertEqual(
            [(entry["compared"], entry["matches"]) for entry in trace["chain"]],
            [(True, False), (True, True)],
        )
        self.assertEqual(trace["steps"][0]["character"], "h")
        self.assertEqual(trace["steps"][0]["codepoint"], ord("h"))
        self.assertEqual(trace["steps"][0]["previous_hash"], 0)
        self.assertEqual(trace["steps"][0]["current_hash"], ord("h") % 8)
        self.assertEqual(
            trace["steps"][-1]["current_hash"],
            trace["bucket_index"],
        )

    def test_visualizer_rejects_non_url_key_with_bad_request(self):
        status, body = self._post_json("/visualize", {"key": "not a URL"})

        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_visualizer_reports_linear_probe_path_and_final_slot(self):
        first_url = "https://example.com/a"
        second_url = "https://example.com/i"
        self._post_json("/shorten", {"url": first_url})
        _status, second_short = self._post_json(
            "/shorten",
            {"url": second_url},
        )

        status, trace = self._post_json(
            "/visualize",
            {
                "key": second_url,
                "collision_resolution": "linear_probing",
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(trace["collision_resolution"], "linear_probing")
        self.assertEqual(trace["initial_bucket"], trace["probes"][0]["slot_index"])
        self.assertEqual(trace["initial_bucket"], 0)
        self.assertEqual(trace["probes"][0]["key"], first_url)
        self.assertEqual(trace["probes"][0]["matches"], False)
        self.assertEqual(trace["probes"][1]["key"], second_url)
        self.assertTrue(trace["probes"][1]["matches"])
        self.assertEqual(trace["final_slot"], trace["probes"][-1]["slot_index"])
        self.assertEqual(trace["final_slot"], 1)
        self.assertEqual(trace["slot_probes"], 2)
        self.assertEqual(trace["value"], second_short["code"])

    def test_visualizer_rejects_unknown_collision_resolution(self):
        status, body = self._post_json(
            "/visualize",
            {
                "key": "https://example.com/a",
                "collision_resolution": "unknown",
            },
        )

        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def _post_json(self, path, payload, headers=None):
        body = json.dumps(payload).encode("utf-8")
        return self._post_raw(path, body, headers)

    def _post_raw(self, path, body, headers=None):
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=request_headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())


if __name__ == "__main__":
    unittest.main()
