"""Unit tests for Jev invoice-demo fixtures and decision composition."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from jev_invoice_demo import (  # noqa: E402
    DEFAULT_INVOICE_COUNT,
    DEFAULT_MIX,
    JEV_INPUT_PRICE_PER_MTOK,
    FAIL_THRESHOLD,
    PASS_THRESHOLD,
    PLANTED_KINDS,
    classify_noul,
    compose_from_response,
    compose_result,
    estimate_cost_usd,
    generate_invoices,
    simulated_response,
    invoice_state,
    jev_questions,
    mix_for_count,
    nouls_from_response,
    public_invoice,
    run_evaluations,
    tally_bars,
    usage_from_response,
)


def test_generate_invoices_default_count_and_unique_ids() -> None:
    invoices = generate_invoices()
    assert len(invoices) == DEFAULT_INVOICE_COUNT
    assert len({inv.id for inv in invoices}) == DEFAULT_INVOICE_COUNT
    assert len({inv.invoice_number for inv in invoices}) == DEFAULT_INVOICE_COUNT


def test_generate_invoices_is_deterministic() -> None:
    a = generate_invoices(seed=7)
    b = generate_invoices(seed=7)
    assert [inv.id for inv in a] == [inv.id for inv in b]
    assert [inv.planted_kind for inv in a] == [inv.planted_kind for inv in b]


def test_default_mix_is_present() -> None:
    invoices = generate_invoices()
    counts = {kind: 0 for kind in PLANTED_KINDS}
    for inv in invoices:
        counts[inv.planted_kind] += 1
    assert counts == DEFAULT_MIX


def test_mix_for_count_keeps_every_kind() -> None:
    mix = mix_for_count(40)
    assert set(mix) == set(PLANTED_KINDS)
    assert sum(mix.values()) == 40
    assert all(value >= 1 for value in mix.values())


def test_clean_invoice_amounts_reconcile() -> None:
    clean = next(inv for inv in generate_invoices() if inv.planted_kind == "clean")
    assert clean.final_amount == pytest.approx(clean.approved_amount)
    assert clean.line_item_sum == pytest.approx(clean.final_amount)
    assert clean.change_order is None


def test_overbill_exceeds_approved_without_change_order() -> None:
    over = next(inv for inv in generate_invoices() if inv.planted_kind == "overbill")
    assert over.final_amount > over.approved_amount
    assert over.change_order is None
    assert any("surcharge" in item.description.lower() for item in over.line_items)


def test_missing_scope_keeps_amount_but_substitutes_a_line() -> None:
    missing = next(inv for inv in generate_invoices() if inv.planted_kind == "missing_scope")
    assert missing.final_amount == pytest.approx(missing.approved_amount)
    assert any("substituted" in item.description.lower() for item in missing.line_items)


def test_change_order_documents_the_delta() -> None:
    changed = next(inv for inv in generate_invoices() if inv.planted_kind == "change_order")
    assert changed.change_order is not None
    assert changed.final_amount > changed.approved_amount
    assert "CO-14" in changed.change_order


def test_invoice_state_omits_planted_kind() -> None:
    invoice = generate_invoices()[0]
    state = invoice_state(invoice)
    assert "planted_kind" not in state
    assert "planted" not in state
    assert state["invoice_number"] == invoice.invoice_number
    assert state["line_item_sum_usd"] == pytest.approx(invoice.line_item_sum)
    for inv in generate_invoices():
        dumped = str(invoice_state(inv)).lower()
        assert "planted_kind" not in dumped
        assert "overbill" not in dumped
        assert "missing_scope" not in dumped


def test_public_invoice_omits_planted_kind() -> None:
    invoice = generate_invoices()[0]
    public = public_invoice(invoice)
    assert "planted_kind" not in public
    assert public["id"] == invoice.id
    assert public["approved_amount"] == invoice.approved_amount


def test_public_invoice_carries_approved_scope_lines() -> None:
    by_kind = {inv.planted_kind: inv for inv in generate_invoices()}
    clean = public_invoice(by_kind["clean"])
    assert clean["approved_line_items"] == clean["line_items"]

    missing = public_invoice(by_kind["missing_scope"])
    approved = {item["description"] for item in missing["approved_line_items"]}
    billed = {item["description"] for item in missing["line_items"]}
    assert approved - billed, "the dropped deliverable should only be on the PO side"
    assert billed - approved, "the substitute should only be on the invoice side"

    # The PO lines are UI-only context; the Jev state is unchanged.
    assert "approved_line_items" not in invoice_state(by_kind["clean"])


def test_classify_noul_thresholds() -> None:
    assert classify_noul(PASS_THRESHOLD) == "pass"
    assert classify_noul(0.99) == "pass"
    assert classify_noul(FAIL_THRESHOLD) == "fail"
    assert classify_noul(0.0) == "fail"
    assert classify_noul(0.5) == "review"
    assert classify_noul(0.79) == "review"
    assert classify_noul(0.21) == "review"


def test_compose_result_and_tally_bars() -> None:
    first = compose_result(0.94, 0.12)
    second = compose_result(0.55, 0.81)
    assert first["amount_matches"]["verdict"] == "pass"
    assert first["scope_covered"]["verdict"] == "fail"
    bars = tally_bars([first, second])
    assert bars["amount_matches"] == {"pass": 1, "review": 1, "fail": 0}
    assert bars["scope_covered"] == {"pass": 1, "review": 0, "fail": 1}


def test_jev_questions_are_two_nouls() -> None:
    questions = jev_questions()
    assert set(questions) == {"amount_matches", "scope_covered"}
    for spec in questions.values():
        assert spec["type"] == "noul"
        assert "instructions" in spec
        assert set(spec["criteria"]) == {"true", "false"}


def test_nouls_from_sdk_style_response() -> None:
    response = SimpleNamespace(
        nouls={
            "amount_matches": SimpleNamespace(noul=0.91),
            "scope_covered": SimpleNamespace(noul=0.17),
        }
    )
    assert nouls_from_response(response) == pytest.approx((0.91, 0.17))
    composed = compose_from_response(response)
    assert composed["amount_matches"]["verdict"] == "pass"
    assert composed["scope_covered"]["verdict"] == "fail"


def test_usage_and_cost_from_response() -> None:
    sdk_style = SimpleNamespace(usage=SimpleNamespace(input_tokens=420, output_tokens=12))
    assert usage_from_response(sdk_style) == (420, 12)
    assert usage_from_response({"usage": {"input_tokens": 100, "output_tokens": None}}) == (100, 0)
    assert usage_from_response(simulated_response("clean")) == (0, 0)
    # Jev bills input only: 1M input tokens at the list price, output free.
    assert estimate_cost_usd(1_000_000) == pytest.approx(JEV_INPUT_PRICE_PER_MTOK)
    assert estimate_cost_usd(250_000, price_per_mtok=0.04) == pytest.approx(0.01)
    assert estimate_cost_usd(0) == 0


def test_nouls_from_raw_dict_response() -> None:
    response = {
        "answers": {
            "amount_matches": {"type": "noul", "noul": 0.44},
            "scope_covered": {"type": "noul", "noul": 0.88},
        }
    }
    assert nouls_from_response(response) == pytest.approx((0.44, 0.88))


def test_run_evaluations_uses_injected_ask() -> None:
    invoices = generate_invoices(n=6, seed=1)
    seen: list[str] = []

    async def ask(state: dict, questions: dict) -> SimpleNamespace:
        seen.append(state["invoice_number"])
        assert set(questions) == {"amount_matches", "scope_covered"}
        kind = next(inv.planted_kind for inv in invoices if inv.invoice_number == state["invoice_number"])
        if kind in {"overbill", "underbill", "extra_scope"}:
            amount, scope = 0.08, 0.90
        elif kind == "missing_scope":
            amount, scope = 0.93, 0.11
        elif kind == "ambiguous":
            amount, scope = 0.52, 0.61
        else:
            amount, scope = 0.95, 0.92
        return SimpleNamespace(
            nouls={
                "amount_matches": SimpleNamespace(noul=amount),
                "scope_covered": SimpleNamespace(noul=scope),
            },
            usage=SimpleNamespace(input_tokens=300, output_tokens=8),
        )

    async def collect() -> list[dict]:
        return [event async for event in run_evaluations(invoices, ask, concurrency=3)]

    events = asyncio.run(collect())
    assert len(events) == 6
    assert set(seen) == {inv.invoice_number for inv in invoices}
    assert all(event["ok"] for event in events)
    assert all(event["input_tokens"] == 300 and event["output_tokens"] == 8 for event in events)
    by_id = {event["id"]: event for event in events}
    missing = next(inv for inv in invoices if inv.planted_kind == "missing_scope")
    assert by_id[missing.id]["amount_matches"]["verdict"] == "pass"
    assert by_id[missing.id]["scope_covered"]["verdict"] == "fail"


def test_simulated_response_maps_planted_kinds() -> None:
    clean = compose_from_response(simulated_response("clean"))
    assert clean["amount_matches"]["verdict"] == "pass"
    assert clean["scope_covered"]["verdict"] == "pass"
    over = compose_from_response(simulated_response("overbill"))
    assert over["amount_matches"]["verdict"] == "fail"
    missing = compose_from_response(simulated_response("missing_scope"))
    assert missing["amount_matches"]["verdict"] == "pass"
    assert missing["scope_covered"]["verdict"] == "fail"
    ambiguous = compose_from_response(simulated_response("ambiguous"))
    assert ambiguous["amount_matches"]["verdict"] == "review"


def test_run_evaluations_surfaces_ask_errors() -> None:
    invoices = generate_invoices(n=2, seed=2)

    async def ask(state: dict, questions: dict) -> SimpleNamespace:
        raise RuntimeError("jev unavailable")

    async def collect() -> list[dict]:
        return [event async for event in run_evaluations(invoices, ask, concurrency=2)]

    events = asyncio.run(collect())
    assert len(events) == 2
    assert all(event["ok"] is False for event in events)
    assert all("jev unavailable" in event["error"] for event in events)
