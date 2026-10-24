"""Local-only end-to-end transport coverage, no PySide6 needed."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from urllib.parse import parse_qs, urlsplit

import pytest

from core.core import (
    PREVIEW_LIMIT, SUPPORTED_METHODS, RequestCancelled, RequestSpec, curl_command,
    execute, format_content, prepare,
)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/echo?from=redirect")
            self.end_headers()
            return
        if parts.path == "/binary":
            output = bytes(range(256))
            content_type = "application/octet-stream"
        elif parts.path == "/large":
            output = b"x" * (PREVIEW_LIMIT + 100)
            content_type = "text/plain"
        else:
            output = json.dumps({"path": parts.path, "query": parse_qs(parts.query), "verb": "GET"}).encode()
            content_type = "application/json"
        self._respond(output, content_type)

    def do_POST(self):
        self._echo_method()

    def do_PUT(self):
        self._echo_method()

    def do_PATCH(self):
        self._echo_method()

    def do_DELETE(self):
        self._echo_method()

    def do_OPTIONS(self):
        self._echo_method()

    def do_QUERY(self):
        if not self.headers.get("Content-Type", "").strip():
            self.send_error(400, "QUERY needs Content-Type")
            return
        self._echo_method()

    def do_HEAD(self):
        # HEAD must not return a payload even if the corresponding GET would.
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "0")
        self.send_header("X-Echo-Method", "HEAD")
        self.end_headers()

    def _echo_method(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        parts = urlsplit(self.path)
        data = {
            "method": self.command,
            "path": parts.path,
            "query": parse_qs(parts.query),
            "body": body.decode("utf-8"),
            "content_type": self.headers.get("Content-Type"),
            "authorization": self.headers.get("Authorization"),
            "x-test": self.headers.get("X-Test"),
        }
        self._respond(json.dumps(data).encode(), "application/json")

    def _respond(self, content, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except BrokenPipeError:
            pass

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def url():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join()


def test_duplicate_query_keys_and_success(url):
    result = execute(RequestSpec(url=url + "/echo?existing=ok", params=[["q", "alpha"], ["q", "beta"]]))
    assert result.status == 200
    body = json.loads(result.content)
    assert body["query"]["q"] == ["alpha", "beta"]
    assert body["query"]["existing"] == ["ok"]
    assert result.elapsed_ms >= 0


def test_json_post_including_null(url):
    for payload in ('{"hello": "world"}', "null", "false", "0"):
        result = execute(RequestSpec(method="POST", url=url, body_mode="JSON", body_text=payload))
        echoed = json.loads(result.content)
        assert json.loads(echoed["body"]) == json.loads(payload)
        assert echoed["content_type"] == "application/json"


def test_bearer_and_basic(url):
    bearer = execute(RequestSpec(method="POST", url=url, auth_mode="Bearer", token="abc"))
    assert json.loads(bearer.content)["authorization"] == "Bearer abc"
    basic = execute(RequestSpec(method="POST", url=url, auth_mode="Basic", username="a", password="b"))
    assert json.loads(basic.content)["authorization"] == "Basic YTpi"


def test_urlencoded_form_and_text(url):
    form = execute(RequestSpec(method="POST", url=url, body_mode="Form", form=[["a", "hi there"], ["a", "two"]]))
    echoed = json.loads(form.content)
    assert echoed["body"] == "a=hi+there&a=two"
    assert echoed["content_type"] == "application/x-www-form-urlencoded"
    plain = execute(RequestSpec(method="POST", url=url, body_mode="Text", body_text="💜 ß"))
    assert json.loads(plain.content)["body"] == "💜 ß"


def test_redirects_and_preview(url):
    result = execute(RequestSpec(url=url + "/redirect"))
    assert len(result.redirects) == 1
    assert result.final_url.endswith("/echo?from=redirect")
    raw = execute(RequestSpec(url=url + "/binary"))
    preview, pretty = format_content(raw)
    assert "hexadecimal preview" in preview
    assert not pretty


def test_large_truncated(url):
    result = execute(RequestSpec(url=url + "/large"))
    assert result.preview_truncated
    assert len(result.content) == PREVIEW_LIMIT


def test_cancelled_prior_to_dispatch(url):
    event = Event()
    event.set()
    with pytest.raises(RequestCancelled):
        execute(RequestSpec(url=url), event)


def test_invalid_input():
    with pytest.raises(ValueError):
        prepare(RequestSpec(url="ftp://example.org/file"))
    with pytest.raises(ValueError):
        prepare(RequestSpec(url="https://example.com", body_mode="JSON", body_text="{"))
    with pytest.raises(ValueError):
        prepare(RequestSpec(url="https://example.com", auth_mode="Bearer", token=""))


def test_redaction_and_reimport():
    spec = RequestSpec(url="https://example.com/path?api_key=mysecret&safe=good", params=[["token", "important"], ["q", "hi"]], headers=[["Authorization", "abc"], ["X-User", "Alice"]], auth_mode="Bearer", token="anothersecret")
    data = spec.export()
    serialized = json.dumps(data)
    assert "mysecret" not in serialized
    assert "important" not in serialized
    assert "anothersecret" not in serialized
    assert "Alice" in serialized
    assert RequestSpec.from_dict(data).url.endswith("api_key=&safe=good")


def test_curl_keeps_correct_method_and_redacts():
    spec = RequestSpec(method="POST", url="https://example.org/a?token=abc", params=[["q", "hello world"]], auth_mode="Bearer", token="oops", body_mode="Form", form=[["client_secret", "secret"], ["x", "1"]])
    cmd = curl_command(spec)
    assert "-X POST" in cmd and "--data-binary" in cmd
    assert "abc" not in cmd and "oops" not in cmd and "secret=secret" not in cmd
    assert "q=hello+world" in cmd


def test_embedded_userinfo_redacted():
    spec = RequestSpec(url="https://alice:secret@example.org/p?key=ok", proxy="http://bob:proxysecret@127.0.0.1:8080")
    exported = str(spec.export())
    assert "secret" not in exported
    assert "alice" not in exported
    assert "bob" not in exported
    assert "example.org/p?key=ok" in exported


@pytest.mark.parametrize("method", SUPPORTED_METHODS)
def test_every_supported_method_reaches_local_server(url, method):
    """Transport proves every GUI method, not only GET / POST."""
    if method == "HEAD":
        result = execute(RequestSpec(method=method, url=url + "/head-check"))
        assert result.status == 200
        assert result.content == b""
        assert [v for k, v in result.headers if k.lower() == "x-echo-method"] == ["HEAD"]
        return
    mode = "JSON" if method in {"POST", "PUT", "PATCH", "DELETE", "QUERY"} else "None"
    spec = RequestSpec(
        method=method, url=url + "/echo?existing=1",
        params=[["duplicate", "a"], ["duplicate", "b"]],
        headers=[["X-Test", "volt"], ["Accept", "application/json"]],
        body_mode=mode, body_text='{"sent":true}',
    )
    result = execute(spec)
    assert result.status == 200
    data = json.loads(result.content)
    if method == "GET":
        assert data["verb"] == "GET"  # GET uses the original GET-specific handler.
    else:
        assert data["method"] == method
        assert data["content_type"] == ("application/json" if mode == "JSON" else None)
        assert data["body"] == ('{"sent":true}' if mode == "JSON" else "")
        assert data["x-test"] == "volt"
        assert data["query"]["existing"] == ["1"]
        assert data["query"]["duplicate"] == ["a", "b"]
    assert f"-X {method}" in curl_command(spec)
    reimported = RequestSpec.from_dict(spec.export())
    assert reimported.method == method


@pytest.mark.parametrize("mode,body,expected_type,expected_body", [
    ("JSON", '{"find":"💜"}', "application/json", '{"find":"💜"}'),
    ("Text", "lookup cars", "text/plain; charset=utf-8", "lookup cars"),
    ("Form", "", "application/x-www-form-urlencoded", "field=a+b"),
])
def test_query_body_media_types(url, mode, body, expected_type, expected_body):
    result = execute(RequestSpec(method="QUERY", url=url + "/lookup", body_mode=mode,
                                 body_text=body, form=[["field", "a b"]]))
    assert result.status == 200
    data = json.loads(result.content)
    assert data["method"] == "QUERY"
    assert data["body"] == expected_body
    assert data["content_type"] == expected_type


def test_query_rejects_missing_content_type_and_missing_body():
    with pytest.raises(ValueError, match="QUERY needs a request body"):
        prepare(RequestSpec(method="QUERY", url="http://localhost/"))
    with pytest.raises(ValueError, match="Content-Type"):
        prepare(RequestSpec(method="QUERY", url="http://localhost/", body_mode="JSON",
                            body_text="{}", headers=[["Content-Type", ""]]))


def test_direct_and_imported_unsupported_method():
    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        prepare(RequestSpec(method="BREW", url="http://localhost/"))
    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        RequestSpec.from_dict({"method": "BREW"})


def test_theme_config_and_presets():
    from core.theme import PRESETS, ThemeColors, style_for
    for key, colors in PRESETS.items():
        stylesheet = style_for(colors)
        assert colors.yellow in stylesheet and colors.fuchsia in stylesheet
        assert colors.background in stylesheet
        assert "QPushButton#sendButton" in stylesheet
    customized = ThemeColors("#ffe033", "#f300c4", "#271e37")
    rendered = style_for(customized)
    for field in (customized.yellow, customized.fuchsia, customized.background):
        assert field in rendered
    with pytest.raises(ValueError):
        style_for(ThemeColors("not a color", "#ff00cc", "#110011"))


def test_query_text_curl_includes_content_type():
    spec = RequestSpec(method="QUERY", url="https://example.org/filter", body_mode="Text", body_text="search me")
    command = curl_command(spec)
    assert "-X QUERY" in command
    assert "Content-Type: text/plain; charset=utf-8" in command
    assert "--data-binary" in command
