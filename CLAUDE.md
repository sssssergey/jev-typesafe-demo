# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A demo of Jev.TypeSafe "System One" invoice validation: a Python server fans a batch of synthetic invoices out to Jev, and a React page streams the pass / review / fail verdicts as they arrive.

## Commands

Python has no manifest; the runtime deps are `python-dotenv` (always) and `typesafe-sdk` (only for live mode), plus `pytest` for tests. Install them by hand.

```
python -m pytest tests -q                        # all tests (~2s, no network)
python -m pytest tests -q -k test_name           # one test
python tools/run_jev_invoice_demo.py             # serve on http://127.0.0.1:8765
python tools/run_jev_invoice_demo.py --simulate  # force local stand-in answers
python tools/run_jev_invoice_demo.py --count 40  # smaller batch
```

The server builds the React app into `jev_invoice_demo/dist/` on first run (runs `npm install` + `npm run build` itself). For hot reload, keep the server running and in `jev_invoice_demo/` run `npm run dev`; Vite proxies `/api` to port 8765. After editing UI code without the dev server, delete `dist/` or run `npm run build` so the Python server serves fresh output.

Live mode needs `TYPESAFE_API_KEY` in the environment or a root `.env`. Without it the server silently runs in preview mode and the UI shows a banner.

## Architecture

Three layers, one direction of dependency:

- `tools/jev_invoice_demo.py` is the I/O-free core: deterministic invoice fixtures, the two Noul questions sent to Jev (`amount_matches`, `scope_covered`), threshold classification (noul >= 0.80 pass, <= 0.20 fail, else review), and `run_evaluations`, an async generator that takes an injected `ask` callable. Everything the tests cover lives here.
- `tools/run_jev_invoice_demo.py` wraps the core in a `ThreadingHTTPServer` with an asyncio loop on a background thread. `DemoApp` owns run state; `Broadcaster` replays history to new SSE subscribers on `/api/stream`. It supplies the real `ask` (typesafe-sdk `AsyncTypeSafeClient.system_one`) or a simulated one keyed off each invoice's planted kind.
- `jev_invoice_demo/src/` is the React UI. `useDemo.js` is the only file that talks to the server (`/api/status`, `/api/invoices`, `/api/stream`, `/api/run`, `/api/pause`, `/api/resume`); components are presentational.

Invariants worth keeping:

- Each invoice carries a hidden `planted_kind` (clean, overbill, underbill, missing_scope, extra_scope, change_order, ambiguous). It must never reach Jev or the browser. `invoice_state()` and `public_invoice()` are the two serializers, and tests assert the label is absent from both. `approved_line_items` (the PO lines before defects are planted) goes only to the browser via `public_invoice()` for the approved-vs-delivered scope panel; Jev keeps seeing just the billed lines plus the SOW text.
- Arithmetic stays in code. The line-item sum is precomputed and passed to Jev so the model only judges amount-match and scope-coverage.
- `SIMULATED_NOULS` maps each planted kind to fixed noul pairs; changing a kind's expected verdict means updating both that table and the tests.
- Run cost is estimated in code, not reported by Jev: `usage.input_tokens` from each response times `JEV_INPUT_PRICE_PER_MTOK` (the docs.typesafe.ai/models list price, output tokens free). `TYPESAFE_INPUT_PRICE_PER_MTOK` overrides it; the server reports `cost_usd: null` in preview mode.
- The API key lives only in the server process; `/api/status` reports `has_key` as a boolean and nothing more.
