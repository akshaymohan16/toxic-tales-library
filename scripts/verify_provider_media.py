#!/usr/bin/env python3
"""Read-only SHA-256 verification of this repository's public/provider media."""
import argparse
import errno
import hashlib
from http.client import HTTPException, IncompleteRead
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

REPOSITORY = "akshaymohan16/toxic-tales-library"
BRAND_ID = "7937614"
MAX_BYTES = 100 * 1024 * 1024
MAX_FILES = 16
MAX_ATTEMPTS = 3
TIMEOUT = 20
ROLES = {"source_video", "provider_video", "source_cover", "provider_cover"}
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def validate_url(url, role):
    """Allow only direct media in the repository or this exact Metricool brand."""
    if not isinstance(url, str) or len(url) > 2048 or role not in ROLES:
        raise ValueError("Invalid media URL or role")
    if any(ord(char) < 33 or ord(char) > 126 for char in url) or "\\" in url or "%" in url:
        raise ValueError("Media URL contains unsafe encoding or characters")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.username is not None or parts.password is not None
            or parts.port not in (None, 443) or parts.query or parts.fragment
            or any(segment in {".", ".."} for segment in parts.path.split("/"))):
        raise ValueError("Media URL must be direct HTTPS without credentials or URL modifiers")
    if role.startswith("source_"):
        if (parts.hostname != "akshaymohan16.github.io"
                or not parts.path.startswith("/toxic-tales-library/")):
            raise ValueError("Source URL is outside the allowed repository")
    elif (parts.hostname != "static.metricool.com" or not re.fullmatch(
            r"/planner/[0-9]{4}(?:0[1-9]|1[0-2])/7937614-file-[0-9]+\.(?:mp4|jpe?g|png)", parts.path)):
        raise ValueError("Provider URL is outside the allowed Metricool brand media")
    allowed = (".mp4",) if role.endswith("_video") else (".jpg", ".jpeg", ".png")
    if not parts.path.endswith(allowed):
        raise ValueError("Media extension does not match its role")
    return url


class SafeRedirects(HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 2

    def __init__(self, role):
        self.role = role

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Validate before urllib creates/follows the redirected request.
        validate_url(newurl, self.role)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_request(request):
    if not isinstance(request, dict) or request.get("repository") != REPOSITORY:
        raise ValueError("Request repository boundary mismatch")
    if request.get("brand_id") != BRAND_ID:
        raise ValueError("Request Metricool brand boundary mismatch")
    if not re.fullmatch(r"TT-[0-9]{3,}", str(request.get("episode_id", ""))):
        raise ValueError("Invalid episode identity")
    if not re.fullmatch(r"[0-9a-f]{64}", str(request.get("release_fingerprint", ""))):
        raise ValueError("A SHA-256 release fingerprint is required")
    if "source_commit" in request and not re.fullmatch(r"[0-9a-f]{40}", str(request["source_commit"])):
        raise ValueError("Invalid source commit")
    files = request.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError("Request must contain 1-16 media files")
    seen = set()
    for item in files:
        if not isinstance(item, dict) or item.get("role") not in ROLES:
            raise ValueError("Invalid media record")
        validate_url(item.get("url"), item["role"])
        if item["url"] in seen:
            raise ValueError("Duplicate media URL in request")
        seen.add(item["url"])
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("expected_sha256", ""))):
            raise ValueError("A SHA-256 expected digest is required")
    return request


def transient(error):
    if isinstance(error, HTTPError):
        return error.code in TRANSIENT_HTTP
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, (TimeoutError, socket.timeout, ConnectionResetError, ConnectionAbortedError, IncompleteRead)):
        return True
    if isinstance(reason, socket.gaierror):
        return reason.errno == socket.EAI_AGAIN
    return isinstance(reason, OSError) and reason.errno in {errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNABORTED}


def verify_file(item, opener_factory=None, sleep=time.sleep, max_bytes=MAX_BYTES):
    """Stream one unauthenticated GET, retrying only bounded transient failures."""
    url, role = item["url"], item["role"]
    validate_url(url, role)
    opener = (opener_factory(role) if opener_factory else
              build_opener(ProxyHandler({}), SafeRedirects(role)))
    result = {"role": role, "expected_sha256": item["expected_sha256"], "sha256": None,
              "http_status": None, "bytes": 0, "decision": "fail"}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result.update(attempts=attempt, checked_at=timestamp(), sha256=None, http_status=None,
                      bytes=0, decision="fail")
        result.pop("error", None)
        result.pop("final_url", None)
        try:
            request = Request(url, headers={"User-Agent": "Toxic-Tales-Media-Verification/1.0",
                                           "Accept-Encoding": "identity"}, method="GET")
            with opener.open(request, timeout=TIMEOUT) as response:
                validate_url(response.geturl(), role)
                result["http_status"] = response.getcode()
                result["final_url"] = response.geturl()
                if response.getcode() != 200:
                    raise ValueError("Expected HTTP 200 for complete media")
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdigit() or int(length) > max_bytes):
                    raise ValueError("Invalid Content-Length or media exceeds 100 MiB limit")
                digest = hashlib.sha256()
                while True:
                    chunk = response.read(min(64 * 1024, max_bytes + 1 - result["bytes"]))
                    if not chunk:
                        break
                    result["bytes"] += len(chunk)
                    if result["bytes"] > max_bytes:
                        raise ValueError("Streamed media exceeds 100 MiB limit")
                    digest.update(chunk)
                if length is not None and result["bytes"] != int(length):
                    raise ValueError("Response ended before declared Content-Length")
                result["sha256"] = digest.hexdigest()
                if result["sha256"] != item["expected_sha256"]:
                    raise ValueError("Media SHA-256 does not match expected release bytes")
            result["decision"] = "pass"
            break
        except (HTTPError, URLError, OSError, HTTPException, ValueError) as error:
            if isinstance(error, HTTPError):
                result["http_status"] = error.code
                error.close()
            result["error"] = str(error)
            if attempt == MAX_ATTEMPTS or not transient(error):
                break
            sleep(attempt)
    result["checked_at"] = timestamp()
    return result


def verify(request, opener_factory=None, sleep=time.sleep):
    validate_request(request)  # Validate every target before contacting any server.
    results = {item["url"]: verify_file(item, opener_factory, sleep) for item in request["files"]}
    passed = all(result["decision"] == "pass" for result in results.values())
    return {"checked_at": timestamp(), "repository": REPOSITORY, "brand_id": BRAND_ID,
            "episode_id": request["episode_id"], "release_fingerprint": request["release_fingerprint"],
            "source_commit": request.get("source_commit"), "files": results,
            "passed": passed, "decision": "pass" if passed else "fail"}


def run(root, request_path, report_path):
    if os.environ.get("GITHUB_REPOSITORY", REPOSITORY) != REPOSITORY:
        report = {"checked_at": timestamp(), "files": {}, "passed": False,
                  "decision": "fail", "error": "Execution repository boundary mismatch"}
    elif not (root / request_path).exists():
        report = {"checked_at": timestamp(), "files": {}, "passed": None, "decision": "skip",
                  "reason": "No media-verification request exists; no network requests made"}
    else:
        try:
            with (root / request_path).open("rb") as file:
                raw = file.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise ValueError("Media-verification request exceeds 64 KiB")
            report = verify(json.loads(raw))
        except (ValueError, TypeError, OSError) as error:
            report = {"checked_at": timestamp(), "files": {}, "passed": False,
                      "decision": "fail", "error": str(error)}
    destination = root / report_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, separators=(",", ":"), ensure_ascii=True)
    destination.write_text(serialized + "\n", encoding="utf-8")
    print(serialized, flush=True)
    return 1 if report["passed"] is False else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--request", type=Path, default=Path("automation/media-verification-request.json"))
    parser.add_argument("--report", type=Path, default=Path("work/provider-media-verification.json"))
    args = parser.parse_args()
    raise SystemExit(run(args.root, args.request, args.report))
