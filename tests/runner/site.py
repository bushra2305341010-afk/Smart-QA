"""A tiny local site and a real Chromium for runner tests (`-m browser`, skipped if none)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

PAGES = {
    "/": "<title>Home</title><h1>Shop</h1><a href='/form'>Form</a>"
         "<a href='https://evil.example/'>Elsewhere</a><a href='/danger'>Students</a>"
         "<a href='/students/4/delete'>Delete 4</a><a href='/captcha'>Reset</a>"
         "<a href='/missing#top'>Old</a><a href='mailto:x@example.com'>Mail</a>",
    "/form": """<title>Form</title>
      <label>Email <input id=e></label>
      <label>Password <input id=p type=password></label>
      <label>Country <select id=c><option>BD</option><option>IN</option></select></label>
      <label><input type=checkbox id=t> I agree</label>
      <label>Age <input id=a type=number min=5 max=18 required></label>
      <label>Note <textarea maxlength=200></textarea></label>
      <input type=hidden name=csrf value=x>
      <button onclick="document.getElementById('out').textContent =
        'Saved ' + document.getElementById('e').value + ' ' +
        (document.getElementById('p').value.length) + ' ' +
        document.getElementById('c').value + ' ' + document.getElementById('t').checked;
        console.error('boom');">Save</button>
      <p id=out></p>""",
    "/danger": """<title>Students</title>
      <button aria-label="Delete student" onclick="fetch('/api/students/1',{method:'DELETE'})">X</button>  # noqa: E501
      <button onclick="fetch('/api/students/1/delete',{method:'POST'})">Archive</button>
      <p>Student list</p>""",
    "/captcha": "<title>Reset</title><p>Please tick I'm not a robot</p>",
    "/login": "<title>Log in</title><form><label>Password <input type=password></label>"
              "<button>Log in</button></form>",
    "/misc": """<title>Misc</title><input placeholder="Search" id=q>
      <button data-testid="go" onclick="fetch('/boom').then(()=>{document.getElementById('r')
        .textContent='Done ' + document.getElementById('q').value})">Go</button>
      <p id=r></p>""",
    "/flaky": "<title>Flaky</title><p id=x></p><script>"
              "setTimeout(()=>{document.getElementById('x').textContent='Ready'}, 50)</script>",
}  # fmt: skip


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def _send(self, code: int, body: str) -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/slow":
            time.sleep(1.5)
        if self.path == "/boom":
            self._send(500, "oops")
            return
        if self.path == "/down":
            self._send(503, "<title>Unavailable</title>")
            return
        page = PAGES.get(self.path.split("?")[0])
        self._send(200 if page else 404, page or "<title>404</title>")

    def do_POST(self) -> None:
        self.server.hits.append(("POST", self.path))  # type: ignore[attr-defined]
        self._send(200, "{}")

    def do_DELETE(self) -> None:
        self.server.hits.append(("DELETE", self.path))  # type: ignore[attr-defined]
        self._send(200, "{}")


@pytest.fixture(scope="session")
def site() -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.hits = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")  # sync Playwright owns an event loop: close it per module
def chromium() -> Iterator[Any]:
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as pw:
        browser = None
        for channel in (None, "chrome"):
            try:
                browser = pw.chromium.launch(channel=channel, headless=True)
                break
            except Error:
                continue
        if browser is None:
            pytest.skip("No Chromium available (uv run playwright install chromium)")
        yield browser
        browser.close()
