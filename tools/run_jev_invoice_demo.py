"""
Serve the Jev.TypeSafe invoice-validation demo and stream live System One results.

Usage:
    python tools/run_jev_invoice_demo.py [--host 127.0.0.1] [--port 8765]

Serves the React app in jev_invoice_demo/ (builds dist/ on first run).
For hot reload: run this server, then `npm run dev` in jev_invoice_demo/.

With TYPESAFE_API_KEY in the environment or .env, Start calls Jev live.
Without a key, Start runs a local preview so the page still demonstrates
throughput. The key stays on this process and is never written into the HTML.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from jev_invoice_demo import (  # noqa: E402
    DEFAULT_INVOICE_COUNT,
    empty_bar_counts,
    generate_invoices,
    public_invoice,
    run_evaluations,
    simulated_response,
    tally_bars,
)

UI_DIR = PROJECT_ROOT / "jev_invoice_demo"
UI_DIST = UI_DIR / "dist"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_CONCURRENCY = 12


def has_api_key() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip())


def ensure_ui_build() -> Path:
    index = UI_DIST / "index.html"
    if index.exists():
        return UI_DIST
    if not (UI_DIR / "package.json").exists():
        raise FileNotFoundError(f"React app missing at {UI_DIR}")
    print(f"Building React UI in {UI_DIR} …")
    subprocess.run(["npm", "install"], cwd=UI_DIR, check=True)
    subprocess.run(["npm", "run", "build"], cwd=UI_DIR, check=True)
    if not index.exists():
        raise FileNotFoundError(f"React build did not produce {index}")
    return UI_DIST


def _safe_ui_file(rel: str) -> Path | None:
    target = (UI_DIST / rel).resolve()
    root = UI_DIST.resolve()
    if target != root and root not in target.parents:
        return None
    if target.is_file():
        return target
    return None


class Broadcaster:
    def __init__(self) -> None:
        self._subs: list[queue.Queue[dict[str, Any] | None]] = []
        self._history: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._history = []

    def subscribe(self) -> queue.Queue[dict[str, Any] | None]:
        q: queue.Queue[dict[str, Any] | None] = queue.Queue()
        with self._lock:
            for event in self._history:
                q.put(event)
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any] | None]) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def emit(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._history.append(event)
            subs = list(self._subs)
        for q in subs:
            q.put(event)


class DemoApp:
    def __init__(
        self,
        invoice_count: int = DEFAULT_INVOICE_COUNT,
        *,
        simulate: bool = False,
    ) -> None:
        self.simulate = simulate or not has_api_key()
        self.invoices = generate_invoices(invoice_count)
        self.public_invoices = [public_invoice(inv) for inv in self.invoices]
        self.bus = Broadcaster()
        self._lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()
        self.status = "idle"
        self.done = 0
        self.results: list[dict[str, Any]] = []
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self._pause = threading.Event()
        self._pause.set()
        self._run_task: asyncio.Task[Any] | None = None

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            elapsed_ms = 0.0
            if self.started_at is not None:
                end = self.finished_at if self.finished_at is not None else time.perf_counter()
                elapsed_ms = (end - self.started_at) * 1000
            per_sec = (self.done / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0
            return {
                "has_key": has_api_key(),
                "simulate": self.simulate,
                "invoice_count": len(self.invoices),
                "concurrency": DEFAULT_CONCURRENCY,
                "run": {
                    "status": self.status,
                    "done": self.done,
                    "total": len(self.invoices),
                    "elapsed_ms": elapsed_ms,
                    "per_sec": per_sec,
                    "bars": tally_bars(self.results) if self.results else empty_bar_counts(),
                },
            }

    def start(self, concurrency: int = DEFAULT_CONCURRENCY) -> dict[str, Any]:
        if not has_api_key() and not self.simulate:
            return {"ok": False, "error": "TYPESAFE_API_KEY is not set"}
        fut = asyncio.run_coroutine_threadsafe(self._start(concurrency), self._loop)
        return fut.result(timeout=5)

    def pause(self) -> dict[str, Any]:
        fut = asyncio.run_coroutine_threadsafe(self._pause_run(), self._loop)
        return fut.result(timeout=5)

    def resume(self) -> dict[str, Any]:
        fut = asyncio.run_coroutine_threadsafe(self._resume_run(), self._loop)
        return fut.result(timeout=5)

    async def _start(self, concurrency: int) -> dict[str, Any]:
        if self._run_task is not None and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
        self.bus.reset()
        self.status = "running"
        self.done = 0
        self.results = []
        self.started_at = time.perf_counter()
        self.finished_at = None
        self._pause.set()
        self.bus.emit({"type": "hello", "total": len(self.invoices), "concurrency": concurrency})
        self._run_task = asyncio.create_task(self._run(concurrency))
        return {"ok": True, "total": len(self.invoices), "concurrency": concurrency}

    async def _pause_run(self) -> dict[str, Any]:
        if self.status != "running":
            return {"ok": False, "error": "no running batch"}
        self._pause.clear()
        self.status = "paused"
        self.bus.emit({"type": "status", "status": "paused", **self._progress_payload()})
        return {"ok": True, "status": "paused"}

    async def _resume_run(self) -> dict[str, Any]:
        if self.status != "paused":
            return {"ok": False, "error": "batch is not paused"}
        self._pause.set()
        self.status = "running"
        self.bus.emit({"type": "status", "status": "running", **self._progress_payload()})
        return {"ok": True, "status": "running"}

    def _progress_payload(self) -> dict[str, Any]:
        elapsed_ms = 0.0
        if self.started_at is not None:
            elapsed_ms = (time.perf_counter() - self.started_at) * 1000
        per_sec = (self.done / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0
        return {
            "done": self.done,
            "total": len(self.invoices),
            "elapsed_ms": elapsed_ms,
            "per_sec": per_sec,
            "bars": tally_bars(self.results) if self.results else empty_bar_counts(),
        }

    async def _before_ask(self) -> None:
        while not self._pause.is_set():
            await asyncio.sleep(0.05)

    async def _run(self, concurrency: int) -> None:
        if self.simulate:
            await self._drain(self._simulated_ask(), concurrency)
            return

        try:
            from typesafe_sdk import AsyncTypeSafeClient
        except ImportError:
            self.status = "error"
            self.bus.emit(
                {
                    "type": "error",
                    "error": "typesafe-sdk is not installed. pip install typesafe-sdk",
                }
            )
            return

        async with AsyncTypeSafeClient() as client:

            async def ask(state: dict[str, Any], questions: dict[str, dict[str, Any]]) -> Any:
                return await client.system_one(state=state, questions=questions)

            await self._drain(ask, concurrency)

    def _simulated_ask(self):
        by_number = {inv.invoice_number: inv for inv in self.invoices}

        async def ask(state: dict[str, Any], questions: dict[str, dict[str, Any]]) -> Any:
            del questions
            await asyncio.sleep(0.08)
            invoice = by_number[state["invoice_number"]]
            return simulated_response(invoice.planted_kind)

        return ask

    async def _drain(self, ask, concurrency: int) -> None:
        try:
            async for event in run_evaluations(
                self.invoices,
                ask,
                concurrency=concurrency,
                before_ask=self._before_ask,
            ):
                if event.get("ok"):
                    self.results.append(event)
                self.done += 1
                payload = {**event, "type": "result", **self._progress_payload()}
                self.bus.emit(payload)
        except asyncio.CancelledError:
            self.status = "idle"
            self.bus.emit({"type": "status", "status": "idle", **self._progress_payload()})
            raise

        self.finished_at = time.perf_counter()
        self.status = "done"
        self.bus.emit({"type": "done", **self._progress_payload()})


APP: DemoApp | None = None


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[jev-demo] {self.address_string()} - {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        self._send(code, _json_bytes(payload), "application/json; charset=utf-8")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _serve_ui(self, path: str) -> None:
        rel = "index.html" if path in {"/", "/index.html"} else unquote(path).lstrip("/")
        target = _safe_ui_file(rel)
        if target is None and not path.startswith("/api/"):
            target = _safe_ui_file("index.html")
        if target is None:
            self._send_json(404, {"error": "not found"})
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        self._send(200, target.read_bytes(), content_type)

    def do_GET(self) -> None:  # noqa: N802
        assert APP is not None
        path = urlparse(self.path).path
        if path == "/api/status":
            self._send_json(200, APP.snapshot())
            return
        if path == "/api/invoices":
            self._send_json(200, {"invoices": APP.public_invoices})
            return
        if path == "/api/stream":
            self._stream()
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        self._serve_ui(path)

    def do_POST(self) -> None:  # noqa: N802
        assert APP is not None
        path = urlparse(self.path).path
        if path == "/api/run":
            body = self._read_json()
            concurrency = int(body.get("concurrency") or DEFAULT_CONCURRENCY)
            concurrency = max(1, min(concurrency, 32))
            result = APP.start(concurrency)
            self._send_json(200 if result.get("ok") else 400, result)
            return
        if path == "/api/pause":
            result = APP.pause()
            self._send_json(200 if result.get("ok") else 400, result)
            return
        if path == "/api/resume":
            result = APP.resume()
            self._send_json(200 if result.get("ok") else 400, result)
            return
        self._send_json(404, {"error": "not found"})

    def _stream(self) -> None:
        assert APP is not None
        q = APP.bus.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                if event is None:
                    break
                payload = json.dumps(event)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            APP.bus.unsubscribe(q)


def main() -> int:
    parser = argparse.ArgumentParser(description="Jev.TypeSafe invoice validation demo")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--count", type=int, default=DEFAULT_INVOICE_COUNT)
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Force local preview answers even if TYPESAFE_API_KEY is set",
    )
    args = parser.parse_args()

    try:
        ensure_ui_build()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"could not build React UI: {exc}", file=sys.stderr)
        print("From the repo root: cd jev_invoice_demo && npm install && npm run build", file=sys.stderr)
        return 1

    global APP
    APP = DemoApp(invoice_count=args.count, simulate=args.simulate)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Jev invoice demo: http://{args.host}:{args.port}")
    print(f"React UI: {UI_DIST}")
    if APP.simulate:
        print("Preview mode — answers are local stand-ins. Set TYPESAFE_API_KEY for live Jev.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
        APP._loop.call_soon_threadsafe(APP._loop.stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
