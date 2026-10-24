# FLukeQuery — Request Studio

A standalone-source, desktop HTTP request client for Windows, built with **PySide6 + HTTPX**. Brighter violet panels, saturated fuchsia gradients, lemon-yellow interaction highlights, subtle sheen. The yellow, fuchsia and background colors are customizable.

## Launch (Windows)

Install dependencies into your existing Python environment (no virtualenv required):

```powershell
py -m pip install -r requirements.txt
py -m core
```

Or double-click `install.bat` once, then `run.bat` to launch. Both use the Windows Python launcher (`py`) when available, or `python` otherwise.

Tested with Python 3.11+ syntax; requires a current PySide6-supported Python version. PySide6 and HTTPX are the only runtime dependencies.

## Features

- Methods: **GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, QUERY**
- Each method is dispatched using `httpx.Client.stream(method=...)`, with no GET-specific routing. The local test server implements all eight methods and verifies each round-trip.
- **QUERY** is defined by [RFC 10008 (June 2026)](https://www.rfc-editor.org/rfc/rfc10008.html): safe/idempotent body-bearing requests. Switching to QUERY initializes a JSON `{}` body if none is selected; JSON, Text, and Form body modes set appropriate Content-Type headers. The destination server or proxy still must support QUERY (otherwise 405/501 or proxy-level rejection can occur).
- **Theme ✦** button: choose Vivid (new brighter default), Electric, Classic, or independently set yellow/fuchsia/background in a native color picker. Theme choices persist through `QSettings` and update editors and JSON syntax coloring.
- URL editor; duplicate-friendly query parameter, header and form tables
- JSON validation and JSON/text/form request bodies
- Bearer and Basic authentication
- Timeout, follow redirects, TLS verification and proxy controls
- Asynchronous GUI execution via Qt thread-pool; Send/Cancel
- HTTP status, elapsed wall time, HTTP protocol, payload size
- Response preview with pretty-printed JSON, simple syntax highlighting, text search, headers, cookies, redirects
- Binary response inspection as hexadecimal; save raw buffered bytes
- Per-session request history; named requests saved between launches
- Import/export request JSON; Copy cURL command (POSIX/Git Bash/WSL syntax)
- Shortcuts: Ctrl+Enter or F5 send, Ctrl+S save, Ctrl+L focus URL, Ctrl+Shift+C copy cURL

## Privacy and behavior

- Request history stays in memory and is cleared when the app closes.
- Named requests and exported request JSON **remove bearer tokens, Basic passwords, credentials embedded as URL/proxy userinfo, and values whose field names look sensitive**; names/users are retained.
- **Freeform body text and URL paths are not sanitized.** Review JSON bodies, URL paths and unusual query-string secrets before explicitly saving/exporting. URL query parameters matching common secret-name patterns are scrubbed, but unusual names and URL paths are not.
- The cURL clipboard command excludes bearer/Basic auth, cookies, and named sensitive headers, but **may still include secrets in URL or freeform request bodies**. Review before sharing.
- In-flight requests can be *cooperatively cancelled*; network connection stages may remain blocked up to the configured timeout.
- Response data is buffered **up to 6 MiB** for performance/memory safety. Larger responses are truncated and saved bytes contain *only the preview*. This is an API inspector, not a resumable/download client.
- Uses HTTPX's normal environment proxy and certificate behavior unless overridden. No telemetry.
- Credentials entered in the Auth tab are kept in memory for the current session.

Saved requests live in `%APPDATA%\FLukeQuery\requests.json` on Windows (or `~/.config/FLukeQuery/requests.json` on Unix). On first launch the application imports previous theme settings from Volt HTTP if no FLukeQuery settings exist. Existing saved requests are loaded from the old directory when the new collection file does not exist, and new saves are written to the FLukeQuery directory. The old files are never deleted.

## Verify transport tests

```powershell
py -m pytest -q tests
```

Tests use a local HTTP server; they make no external requests. Current suite: **31 tests**, covering all eight verbs, QUERY in three body modes, redirects, duplicate parameters, credentials, cURL, truncation, and theme generation. GUI source is compiled for syntax, but visual GUI execution requires a Windows machine with PySide6 installed.

## Material-style widgets (0.3 development)

Reusable native Qt controls are in `core/material_widgets.py`: `MaterialButton`, `MaterialLineEdit`, `MaterialComboBox`, `MaterialCheckBox`, `MaterialCard`, `MaterialTabBar` and `MaterialTabWidget`. They use Qt controls rather than web-rendered widgets and preserve the existing theme picker. Hover elevation is animated on buttons; request and response panels use card elevation.

`run.bat` now launches `python -m core` (or `py -m core`). Package imports are relative and the entry point also accepts direct-file execution from IDEs. Install dependencies with `install.bat` before launching. This development branch changes no HTTP transport semantics.

## Translucent Material appearance

**Theme ✦** now offers two independent settings:

- **Surface glass (0–85%)** adjusts only the alpha channel of sidebar/cards,
  input fields, toolbar, tabs and tonal buttons. Labels and body text stay opaque,
  and the method-popup menu stays solid for legibility. Default: 55%.
- **Window opacity (85–100%)** uses Qt's native top-level-window opacity on
  platforms that support it. Values below 100% allow the desktop to show through,
  but also fade text and controls. Default: 100% (crisp text).

The root canvas has a subtle, palette-derived background gradient to make
surface translucency visible. This is native alpha compositing, **not** Windows
Acrylic or a desktop blur effect. Both settings are saved in QSettings and
can be adjusted without restarting.
