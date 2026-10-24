"""HTTP transport and serializable request model. No GUI dependencies."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from threading import Event
from time import perf_counter
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

PREVIEW_LIMIT = 6 * 1024 * 1024
# All entries are sent through httpx.Client.stream(method=...), not method-specific helper calls.
SUPPORTED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "QUERY")
SENSITIVE_KEY = re.compile(r"(?:authorization|api[-_]?key|secret|password|passwd|token|credential|cookie|session|private[-_]?key)", re.I)


class RequestCancelled(Exception):
    pass


@dataclass
class RequestSpec:
    method: str = "GET"
    url: str = "https://httpbin.org/get"
    params: list[list[str]] = field(default_factory=list)
    headers: list[list[str]] = field(default_factory=list)
    body_mode: str = "None"  # None, JSON, Text, Form
    body_text: str = ""
    form: list[list[str]] = field(default_factory=list)
    auth_mode: str = "None"  # None, Bearer, Basic
    username: str = ""
    password: str = ""
    token: str = ""
    timeout: float = 30.0
    follow_redirects: bool = True
    verify_tls: bool = True
    proxy: str = ""

    def export(self, *, redact: bool = True) -> dict[str, Any]:
        d = asdict(self)
        if redact:
            split_url = urlsplit(d["url"])
            # Strip username:password@ from URLs and proxy URLs.
            split_url = split_url._replace(netloc=split_url.netloc.rsplit("@", 1)[-1])
            proxy_parts = urlsplit(d["proxy"])
            if proxy_parts.netloc:
                d["proxy"] = urlunsplit(proxy_parts._replace(netloc=proxy_parts.netloc.rsplit("@", 1)[-1]))
            if split_url.query:
                sanitized_query = urlencode([
                    (key, "" if SENSITIVE_KEY.search(key) else val)
                    for key, val in parse_qsl(split_url.query, keep_blank_values=True)
                ])
                split_url = split_url._replace(query=sanitized_query)
            d["url"] = urlunsplit(split_url)
            d["password"] = ""
            d["token"] = ""
            d["headers"] = [[key, ""] if SENSITIVE_KEY.search(key) else [key, value]
                            for key, value in d["headers"]]
            d["params"] = [[key, ""] if SENSITIVE_KEY.search(key) else [key, value]
                           for key, value in d["params"]]
            d["form"] = [[key, ""] if SENSITIVE_KEY.search(key) else [key, value]
                         for key, value in d["form"]]
            # Body may contain arbitrary credentials, so leave body by user choice.
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RequestSpec:
        allowed = set(cls.__dataclass_fields__)
        clean = {k: v for k, v in raw.items() if k in allowed}
        spec = cls(**clean)
        if spec.method not in SUPPORTED_METHODS:
            raise ValueError("Unsupported HTTP method")
        if spec.body_mode not in {"None", "JSON", "Text", "Form"}:
            raise ValueError("Unsupported body mode")
        if spec.auth_mode not in {"None", "Bearer", "Basic"}:
            raise ValueError("Unsupported authentication mode")
        for pairs in (spec.params, spec.headers, spec.form):
            if not isinstance(pairs, list) or any(not isinstance(p, list) or len(p) != 2 or not all(isinstance(x, str) for x in p) for p in pairs):
                raise ValueError("Invalid key/value rows in request")
        return spec


@dataclass
class ResponseData:
    status: int
    reason: str
    final_url: str
    elapsed_ms: float
    headers: list[list[str]]
    cookies: list[list[str]]
    redirects: list[str]
    content: bytes
    preview_truncated: bool
    content_type: str
    http_version: str


def _usable_pairs(rows: list[list[str]]) -> list[tuple[str, str]]:
    return [(key.strip(), value) for key, value in rows if key.strip()]


def prepare(spec: RequestSpec) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare Client config and request kwargs, raising on invalid input."""
    if spec.method not in SUPPORTED_METHODS:
        raise ValueError(f"Unsupported HTTP method: {spec.method}")
    if spec.body_mode not in {"None", "JSON", "Text", "Form"}:
        raise ValueError(f"Unsupported body mode: {spec.body_mode}")
    url = spec.url.strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError("Enter a complete http:// or https:// URL")
    try:
        _ = parts.port
    except ValueError as exc:
        raise ValueError(f"Invalid URL port: {exc}") from exc
    if not 0 < float(spec.timeout) <= 300:
        raise ValueError("Timeout must be between 0 and 300 seconds")
    headers = httpx.Headers(_usable_pairs(spec.headers))
    # HTTPX replaces URL query strings when given `params`; merge explicitly.
    parsed_query = parse_qsl(parts.query, keep_blank_values=True)
    parsed_query.extend(_usable_pairs(spec.params))
    request: dict[str, Any] = {
        "method": spec.method,
        "url": urlunsplit(parts._replace(query="")),
        "params": parsed_query,
        "headers": headers,
    }
    if spec.auth_mode == "Bearer":
        if not spec.token.strip():
            raise ValueError("Bearer token is blank")
        headers["Authorization"] = f"Bearer {spec.token.strip()}"
    if spec.auth_mode == "Basic":
        request["auth"] = httpx.BasicAuth(spec.username, spec.password)

    if spec.body_mode == "JSON":
        try:
            parsed_json = json.loads(spec.body_text)
            request["content"] = json.dumps(parsed_json, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if "content-type" not in headers:
                headers["Content-Type"] = "application/json"
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    elif spec.body_mode == "Text":
        request["content"] = spec.body_text.encode("utf-8")
        if "content-type" not in headers:
            headers["Content-Type"] = "text/plain; charset=utf-8"
    elif spec.body_mode == "Form":
        request["content"] = urlencode(_usable_pairs(spec.form)).encode("utf-8")
        if "content-type" not in headers:
            headers["Content-Type"] = "application/x-www-form-urlencoded"

    # RFC 10008 §2/2.1: the query representation needs a declared media type.
    # RFC-compliant servers reject QUERY with an absent Content-Type.
    if spec.method == "QUERY":
        if spec.body_mode == "None":
            raise ValueError("QUERY needs a request body. Select JSON, Text, or Form on the Body tab (RFC 10008).")
        if not headers.get("Content-Type", "").strip():
            raise ValueError("QUERY requires a non-empty Content-Type header (RFC 10008).")

    client_config = {
        "verify": spec.verify_tls,
        "follow_redirects": spec.follow_redirects,
        "timeout": httpx.Timeout(float(spec.timeout)),
        "proxy": spec.proxy.strip() or None,
    }
    return client_config, request


def execute(spec: RequestSpec, cancel: Event | None = None) -> ResponseData:
    cancel = cancel or Event()
    if cancel.is_set():
        raise RequestCancelled("Request cancelled")
    options, request = prepare(spec)
    start = perf_counter()
    with httpx.Client(**options) as client:
        with client.stream(**request) as response:
            payload = bytearray()
            truncated = False
            for chunk in response.iter_bytes():
                if cancel.is_set():
                    raise RequestCancelled("Request cancelled")
                room = PREVIEW_LIMIT - len(payload)
                if len(chunk) > room:
                    payload.extend(chunk[:room])
                    truncated = True
                    break
                payload.extend(chunk)
            if cancel.is_set():
                raise RequestCancelled("Request cancelled")
            elapsed_ms = (perf_counter() - start) * 1000
            history = [f"{r.status_code} {r.request.method} {r.url}" for r in response.history]
            return ResponseData(
                status=response.status_code,
                reason=response.reason_phrase,
                final_url=str(response.url),
                elapsed_ms=elapsed_ms,
                headers=[[key, value] for key, value in response.headers.multi_items()],
                # CookieJar preserves same-name cookies across domains/paths.
                cookies=[[cookie.name, cookie.value] for cookie in response.cookies.jar],
                redirects=history,
                content=bytes(payload),
                preview_truncated=truncated,
                content_type=response.headers.get("content-type", ""),
                http_version=response.http_version,
            )


def is_text_content(content_type: str, content: bytes) -> bool:
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime.startswith("text/") or "json" in mime or "xml" in mime or "javascript" in mime or "yaml" in mime or "graphql" in mime:
        return True
    if b"\x00" in content[:4096]:
        return False
    try:
        content[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def format_content(result: ResponseData, pretty: bool = True) -> tuple[str, bool]:
    if not is_text_content(result.content_type, result.content):
        view = result.content[:65536].hex(" ", 1)
        return "BINARY RESPONSE · hexadecimal preview\n\n" + view, False
    text = result.content.decode("utf-8-sig", errors="replace")
    if pretty and ("json" in result.content_type.lower() or text.lstrip().startswith(("{", "["))):
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            return text, True
        except (ValueError, TypeError):
            pass
    return text, False


def curl_command(spec: RequestSpec) -> str:
    """Generate a POSIX-shell cURL command (Git Bash/WSL); hide named secrets."""
    import shlex

    # Render a shareable command even when a saved Bearer/Basic secret is blank.
    prepared_spec = RequestSpec.from_dict({**spec.export(redact=True), "auth_mode": "None"})
    prepare(prepared_spec)
    parts_url = urlsplit(prepared_spec.url.strip())
    query = parse_qsl(parts_url.query, keep_blank_values=True)
    query.extend(_usable_pairs(spec.params))
    safe_query = [(key, "" if SENSITIVE_KEY.search(key) else val) for key, val in query]
    full_url = urlunsplit(parts_url._replace(query=urlencode(safe_query)))
    parts = ["curl", "-X", spec.method, shlex.quote(full_url)]
    for k, v in _usable_pairs(spec.headers):
        if not SENSITIVE_KEY.search(k):
            parts += ["-H", shlex.quote(f"{k}: {v}")]
    if spec.body_mode == "JSON":
        if not any(key.lower() == "content-type" for key, _ in _usable_pairs(spec.headers)):
            parts += ["-H", shlex.quote("Content-Type: application/json")]
        parts += ["--data-binary", shlex.quote(spec.body_text)]
    elif spec.body_mode == "Text":
        if not any(key.lower() == "content-type" for key, _ in _usable_pairs(spec.headers)):
            parts += ["-H", shlex.quote("Content-Type: text/plain; charset=utf-8")]
        parts += ["--data-binary", shlex.quote(spec.body_text)]
    elif spec.body_mode == "Form":
        if not any(key.lower() == "content-type" for key, _ in _usable_pairs(spec.headers)):
            parts += ["-H", shlex.quote("Content-Type: application/x-www-form-urlencoded")]
        body = urlencode([(key, "" if SENSITIVE_KEY.search(key) else val) for key, val in _usable_pairs(spec.form)])
        parts += ["--data-binary", shlex.quote(body)]
    if not spec.verify_tls:
        parts.append("-k")
    if spec.follow_redirects:
        parts.append("-L")
    if spec.proxy.strip():
        parts += ["--proxy", shlex.quote(prepared_spec.proxy.strip())]
    return " ".join(parts)
