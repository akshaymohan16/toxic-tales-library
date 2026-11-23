import hashlib
from http.client import HTTPException, IncompleteRead
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from verify_provider_media import (BRAND_ID, REPOSITORY, SafeRedirects, run, validate_request,
                                   validate_url, verify, verify_file)

SOURCE = "https://akshaymohan16.github.io/toxic-tales-library/media/tt-008.mp4"
PROVIDER = "https://static.metricool.com/planner/202611/7937614-file-16303245207478276113.mp4"
BODY = b"exact approved media bytes"
SHA = hashlib.sha256(BODY).hexdigest()


def item(url=PROVIDER, role="provider_video", expected=SHA):
    return {"url": url, "role": role, "expected_sha256": expected}


def request():
    return {"repository": REPOSITORY, "brand_id": BRAND_ID, "episode_id": "TT-008",
            "release_fingerprint": "a" * 64, "source_commit": "b" * 40,
            "files": [item(SOURCE, "source_video"), item()]}


class Response(io.BytesIO):
    def __init__(self, body=BODY, url=PROVIDER, status=200, length=None):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = {} if length is None else {"Content-Length": str(length)}

    def geturl(self):
        return self.url

    def getcode(self):
        return self.status


class ProviderMediaTests(unittest.TestCase):
    def test_exact_source_and_brand_video_or_cover_urls_allowed(self):
        validate_request(request())
        for url, role in ((SOURCE, "source_video"), (PROVIDER, "provider_video"),
                          (SOURCE.replace(".mp4", ".jpg"), "source_cover"),
                          (PROVIDER.replace(".mp4", ".jpeg"), "provider_cover")):
            self.assertEqual(validate_url(url, role), url)

    def test_other_hosts_brands_schemes_and_url_modifiers_are_denied(self):
        invalid = [PROVIDER.replace("https:", "http:"), PROVIDER.replace("7937614-file", "123-file"),
                   PROVIDER.replace("static.metricool.com", "static.metricool.com.evil.test"),
                   PROVIDER.replace("static.metricool.com", "user:pass@static.metricool.com"),
                   PROVIDER.replace("static.metricool.com", "static.metricool.com:8443"),
                   PROVIDER + "?token=anything", PROVIDER + "#fragment", PROVIDER.replace("/planner/", "/../planner/"),
                   PROVIDER.replace("/planner/", "/%70lanner/"), PROVIDER.replace("/planner/", "/planner\\"),
                   PROVIDER.replace("202611", "202613"), PROVIDER + "\n"]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url, "provider_video")
        for url in (SOURCE.replace("toxic-tales-library/", "toxic-tales-library-other/"),
                    SOURCE.replace("/media/", "/../media/"), PROVIDER):
            with self.assertRaises(ValueError):
                validate_url(url, "source_video")
        with self.assertRaises(ValueError):
            validate_url(PROVIDER, "provider_cover")

    def test_unsafe_redirect_is_blocked_before_redirect_request_creation(self):
        original = Request(PROVIDER)
        redirect = SafeRedirects("provider_video")
        with patch("urllib.request.HTTPRedirectHandler.redirect_request") as follow:
            for target in ("http://static.metricool.com/planner/202611/7937614-file-1.mp4",
                           "https://evil.test/video.mp4", SOURCE):
                with self.assertRaises(ValueError):
                    redirect.redirect_request(original, None, 302, "Found", {}, target)
            follow.assert_not_called()
        allowed = PROVIDER.replace("16303245207478276113", "999")
        self.assertEqual(redirect.redirect_request(original, None, 302, "Found", {}, allowed).full_url, allowed)

    def test_every_request_record_validated_before_any_network(self):
        factory = Mock()
        for change in ({"repository": "other/repo"}, {"brand_id": "123"}, {"release_fingerprint": "unknown"},
                       {"source_commit": "not-a-commit"}, {"files": []}, {"files": [item()] * 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify({**request(), **change}, factory)
        invalid = request()
        invalid["files"][-1]["url"] = "https://evil.test/evil.mp4"
        with self.assertRaises(ValueError):
            verify(invalid, factory)
        factory.assert_not_called()

    def test_streamed_exact_bytes_pass_with_no_credentials_and_complete_report(self):
        def factory(role):
            opener = Mock()
            opener.open.side_effect = lambda req, timeout: Response(url=req.full_url, length=len(BODY))
            return opener
        result = verify(request(), factory)
        self.assertTrue(result["passed"])
        self.assertEqual(set(result["files"]), {SOURCE, PROVIDER})
        for record in result["files"].values():
            self.assertEqual((record["sha256"], record["bytes"], record["http_status"]), (SHA, len(BODY), 200))
            self.assertEqual(record["attempts"], 1)
            self.assertIn("checked_at", record)

    def test_wrong_hash_and_non200_or_wrong_final_origin_fail_without_retry(self):
        for response, record in ((Response(), item(expected="0" * 64)),
                                 (Response(status=206), item()),
                                 (Response(url="https://evil.test/video.mp4"), item())):
            opener = Mock()
            opener.open.return_value = response
            result = verify_file(record, lambda role: opener, sleep=Mock())
            self.assertEqual(result["decision"], "fail")
            self.assertEqual(result["attempts"], 1)
            self.assertEqual(opener.open.call_count, 1)

    def test_declared_and_streamed_size_limits_and_short_responses_fail(self):
        for response in (Response(length=101), Response(body=b"x" * 101), Response(length=len(BODY) + 1)):
            opener = Mock()
            opener.open.return_value = response
            result = verify_file(item(), lambda role: opener, max_bytes=100)
            self.assertEqual(result["decision"], "fail")
            self.assertLessEqual(result["bytes"], 101)
            self.assertEqual(result["attempts"], 1)

    def test_transient_retry_is_bounded_and_permanent_http_errors_are_not_retried(self):
        opener, sleep = Mock(), Mock()
        opener.open.side_effect = [HTTPError(PROVIDER, 503, "Unavailable", {}, None),
                                   URLError(TimeoutError("timeout")), Response()]
        result = verify_file(item(), lambda role: opener, sleep=sleep)
        self.assertEqual((result["decision"], result["attempts"]), ("pass", 3))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
        for status, attempts in ((503, 3), (404, 1), (403, 1)):
            opener = Mock()
            opener.open.side_effect = HTTPError(PROVIDER, status, "Failure", {}, None)
            result = verify_file(item(), lambda role: opener, sleep=Mock())
            self.assertEqual((result["decision"], result["http_status"], result["attempts"]),
                             ("fail", status, attempts))

    def test_failure_does_not_hide_other_file_results(self):
        def factory(role):
            opener = Mock()
            if role == "provider_video":
                opener.open.side_effect = HTTPError(PROVIDER, 404, "Missing", {}, None)
            else:
                opener.open.return_value = Response(url=SOURCE)
            return opener
        result = verify(request(), factory)
        self.assertFalse(result["passed"])
        self.assertEqual(result["files"][SOURCE]["decision"], "pass")
        self.assertEqual(result["files"][PROVIDER]["http_status"], 404)

    def test_truncated_stream_retries_and_malformed_http_has_structured_failure(self):
        truncated = Response()
        truncated.read = Mock(side_effect=IncompleteRead(b"partial", 100))
        opener = Mock()
        opener.open.side_effect = [truncated, Response()]
        result = verify_file(item(), lambda role: opener, sleep=Mock())
        self.assertEqual((result["decision"], result["attempts"]), ("pass", 2))
        opener = Mock()
        opener.open.side_effect = HTTPException("Malformed response")
        result = verify_file(item(), lambda role: opener, sleep=Mock())
        self.assertEqual((result["decision"], result["attempts"]), ("fail", 1))
        self.assertIn("Malformed response", result["error"])

    def test_response_close_error_cannot_leave_a_pass_decision(self):
        class BrokenClose(Response):
            def __exit__(self, *args):
                super().__exit__(*args)
                raise OSError("Response close failed")
        opener = Mock()
        opener.open.return_value = BrokenClose()
        result = verify_file(item(), lambda role: opener, sleep=Mock())
        self.assertEqual(result["decision"], "fail")
        self.assertIn("close failed", result["error"])

    def test_absent_request_skips_and_malformed_request_fails_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("verify_provider_media.build_opener") as network, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(run(root, Path("request.json"), Path("report.json")), 0)
                self.assertEqual(json.loads(output.getvalue())["decision"], "skip")
                (root / "request.json").write_text("not json", encoding="utf-8")
                self.assertEqual(run(root, Path("request.json"), Path("report.json")), 1)
                self.assertFalse(json.loads((root / "report.json").read_text())["passed"])
                network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
