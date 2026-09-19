"""
Jev.TypeSafe invoice-validation fixtures and decision composition.

I/O-free. Generates a deterministic invoice batch, builds the System One
state + Noul questions, and turns calibrated noul values into pass / fail /
review. Arithmetic (line-item sums, dollar compare) stays in code; Jev only
judges amount-match and scope-coverage.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal, Sequence

Verdict = Literal["pass", "fail", "review"]

DEFAULT_INVOICE_COUNT = 200
PASS_THRESHOLD = 0.80
FAIL_THRESHOLD = 0.20

PLANTED_KINDS = (
    "clean",
    "overbill",
    "underbill",
    "missing_scope",
    "extra_scope",
    "change_order",
    "ambiguous",
)

# Deterministic noul pairs for --simulate / missing-key preview. Not Jev.
SIMULATED_NOULS: dict[str, tuple[float, float]] = {
    "clean": (0.96, 0.94),
    "overbill": (0.07, 0.88),
    "underbill": (0.09, 0.22),
    "missing_scope": (0.93, 0.10),
    "extra_scope": (0.08, 0.11),
    "change_order": (0.91, 0.90),
    "ambiguous": (0.54, 0.58),
}

DEFAULT_MIX: dict[str, int] = {
    "clean": 140,
    "overbill": 16,
    "underbill": 12,
    "missing_scope": 12,
    "extra_scope": 10,
    "change_order": 6,
    "ambiguous": 4,
}

JEV_QUESTIONS: dict[str, dict[str, Any]] = {
    "amount_matches": {
        "type": "noul",
        "instructions": (
            "Does the final billed amount match the approved / purchase-order "
            "amount? Treat a documented change order as a valid adjustment to "
            "the approved amount. Ignore floating-point noise under one dollar. "
            "A line-item sum is provided so you do not have to add the numbers."
        ),
        "criteria": {
            "true": (
                "Final amount equals the approved amount, or differs only by a "
                "written change order that accounts for the delta."
            ),
            "false": (
                "Final amount diverges from the approved amount with no "
                "documented change order that explains the difference."
            ),
        },
    },
    "scope_covered": {
        "type": "noul",
        "instructions": (
            "Does the billed work cover the entire contracted scope in the "
            "statement of work? Every SOW deliverable should appear in the "
            "line items or delivery notes, and no material out-of-scope line "
            "should be billed as if it were in-scope."
        ),
        "criteria": {
            "true": (
                "Every contracted deliverable is billed or confirmed delivered, "
                "and billed lines stay inside the SOW or a written change order."
            ),
            "false": (
                "A contracted deliverable is missing, substituted without "
                "approval, or a material out-of-scope line was billed."
            ),
        },
    },
}


@dataclass(frozen=True)
class LineItem:
    description: str
    amount: float


@dataclass(frozen=True)
class Invoice:
    id: str
    vendor: str
    invoice_number: str
    po_number: str
    service: str
    sow: str
    line_items: tuple[LineItem, ...]
    approved_amount: float
    final_amount: float
    delivery_notes: str
    change_order: str | None
    planted_kind: str

    @property
    def line_item_sum(self) -> float:
        return round(sum(item.amount for item in self.line_items), 2)


# Catalog of professional-services jobs. Amounts are the approved PO totals.
_JOBS: tuple[dict[str, Any], ...] = (
    {
        "vendor": "Northline Advisory",
        "service": "Q3 SOC 2 readiness",
        "approved": 12400.0,
        "sow": "Gap assessment, control-matrix update, and a policy pack covering access, change, and vendor management.",
        "lines": (
            ("SOC 2 gap assessment", 5200.0),
            ("Control-matrix update", 3600.0),
            ("Policy pack (access / change / vendor)", 3600.0),
        ),
        "notes": "All three workstreams delivered to the security committee on 12 Aug.",
    },
    {
        "vendor": "Harborfield Labs",
        "service": "Equipment support retainer",
        "approved": 8600.0,
        "sow": "Quarterly on-site calibration of three spectrometers plus remote parts-and-labor coverage.",
        "lines": (
            ("On-site calibration — unit A", 2200.0),
            ("On-site calibration — unit B", 2200.0),
            ("On-site calibration — unit C", 2200.0),
            ("Remote parts-and-labor retainer", 2000.0),
        ),
        "notes": "Calibration certificates attached for units A–C. Retainer period 1 Jul–30 Sep.",
    },
    {
        "vendor": "Helix Audit Partners",
        "service": "Statutory year-end audit",
        "approved": 18800.0,
        "sow": "Fieldwork, partner review, and issuance of the statutory audit opinion for FY2025.",
        "lines": (
            ("Fieldwork — two weeks", 9600.0),
            ("Partner review", 4200.0),
            ("Statutory opinion issuance", 5000.0),
        ),
        "notes": "Opinion issued 4 Sep. Management letter delivered the same day.",
    },
    {
        "vendor": "Kinetic Frame Studio",
        "service": "Product photography package",
        "approved": 4100.0,
        "sow": "One on-site shoot day, a retouched web gallery, and a 24-print set.",
        "lines": (
            ("On-site shoot day", 2400.0),
            ("Retouched web gallery", 800.0),
            ("24-print set", 900.0),
        ),
        "notes": "Gallery link sent 18 Aug. Prints shipped 20 Aug, tracking in the file.",
    },
    {
        "vendor": "Meridian Tax Counsel",
        "service": "Indirect-tax compliance review",
        "approved": 7200.0,
        "sow": "Nexus study, return-position memo, and a corrected filing pack for four states.",
        "lines": (
            ("Nexus study", 2800.0),
            ("Return-position memo", 2200.0),
            ("Corrected filing pack — 4 states", 2200.0),
        ),
        "notes": "Filing pack submitted to the controller on 22 Aug.",
    },
    {
        "vendor": "Palisade Security",
        "service": "External vulnerability scan",
        "approved": 3400.0,
        "sow": "Authenticated scan of the production /24, prioritized findings report, and a retest of criticals.",
        "lines": (
            ("Authenticated production scan", 1600.0),
            ("Prioritized findings report", 1100.0),
            ("Criticals retest", 700.0),
        ),
        "notes": "Retest cleared the two criticals. Report dated 9 Aug.",
    },
    {
        "vendor": "Oak & River Legal",
        "service": "Vendor-contract refresh",
        "approved": 9600.0,
        "sow": "Redline of the MSA, a DPA addendum, and a playbook for the procurement team.",
        "lines": (
            ("MSA redline", 4200.0),
            ("DPA addendum", 2800.0),
            ("Procurement playbook", 2600.0),
        ),
        "notes": "Executed copies returned 29 Aug. Playbook in the shared drive.",
    },
    {
        "vendor": "Lumen Data Co.",
        "service": "Warehouse KPI dashboard",
        "approved": 15200.0,
        "sow": "Ingest of WMS extracts, three operational dashboards, and a two-hour handover.",
        "lines": (
            ("WMS extract ingest", 5400.0),
            ("Operations dashboards (3)", 7800.0),
            ("Handover workshop", 2000.0),
        ),
        "notes": "Dashboards live in Looker. Handover recorded 1 Sep.",
    },
    {
        "vendor": "Cedarline Facilities",
        "service": "HVAC seasonal service",
        "approved": 5400.0,
        "sow": "Filter replacement, coil clean, and a written performance report for both rooftop units.",
        "lines": (
            ("Filter replacement — RTU-1 and RTU-2", 1600.0),
            ("Coil clean — both units", 2400.0),
            ("Performance report", 1400.0),
        ),
        "notes": "Both units back in spec. Report emailed 7 Aug.",
    },
    {
        "vendor": "Bright Harbor Training",
        "service": "Incident-response tabletop",
        "approved": 6800.0,
        "sow": "Scenario design, a half-day facilitated tabletop, and an after-action report.",
        "lines": (
            ("Scenario design", 1800.0),
            ("Facilitated tabletop (4h)", 3200.0),
            ("After-action report", 1800.0),
        ),
        "notes": "Tabletop held 14 Aug with 11 attendees. AAR circulated 16 Aug.",
    },
    {
        "vendor": "Sable Research Group",
        "service": "Win/loss interview series",
        "approved": 9000.0,
        "sow": "Twelve customer interviews, coded notes, and a findings readout.",
        "lines": (
            ("Customer interviews (12)", 5400.0),
            ("Coded notes", 1800.0),
            ("Findings readout", 1800.0),
        ),
        "notes": "All twelve interviews completed. Readout to sales leadership 28 Aug.",
    },
    {
        "vendor": "Volt & Grain Creative",
        "service": "Brand-system refresh",
        "approved": 11100.0,
        "sow": "Logo lockups, a color-and-type system, and a one-page usage guide.",
        "lines": (
            ("Logo lockups", 4200.0),
            ("Color and type system", 3900.0),
            ("Usage guide", 3000.0),
        ),
        "notes": "Final files in Figma. Usage guide exported 11 Aug.",
    },
)


def classify_noul(noul: float) -> Verdict:
    """Map a calibrated yes-probability onto pass / fail / review."""
    if noul >= PASS_THRESHOLD:
        return "pass"
    if noul <= FAIL_THRESHOLD:
        return "fail"
    return "review"


def compose_result(amount_noul: float, scope_noul: float) -> dict[str, Any]:
    """Attach verdicts to the two Noul answers."""
    return {
        "amount_matches": {
            "noul": float(amount_noul),
            "verdict": classify_noul(amount_noul),
        },
        "scope_covered": {
            "noul": float(scope_noul),
            "verdict": classify_noul(scope_noul),
        },
    }


def empty_bar_counts() -> dict[str, dict[str, int]]:
    return {
        "amount_matches": {"pass": 0, "review": 0, "fail": 0},
        "scope_covered": {"pass": 0, "review": 0, "fail": 0},
    }


def tally_bars(results: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Stack pass / review / fail counts for the two checks."""
    bars = empty_bar_counts()
    for result in results:
        for key in ("amount_matches", "scope_covered"):
            verdict = result[key]["verdict"]
            bars[key][verdict] += 1
    return bars


def mix_for_count(n: int) -> dict[str, int]:
    """Scale the default planted mix to `n`, keeping every kind when n >= 7."""
    if n < 1:
        raise ValueError("invoice count must be at least 1")
    if n == DEFAULT_INVOICE_COUNT:
        return dict(DEFAULT_MIX)

    kinds = list(PLANTED_KINDS)
    if n < len(kinds):
        return {kind: 1 for kind in kinds[:n]}

    raw = []
    total_default = sum(DEFAULT_MIX.values())
    for kind in kinds:
        raw.append(max(1, round(DEFAULT_MIX[kind] * n / total_default)))
    # Adjust rounding so the mix sums to n. Prefer adding/removing cleans.
    delta = n - sum(raw)
    by_kind = {kind: raw[i] for i, kind in enumerate(kinds)}
    by_kind["clean"] = max(1, by_kind["clean"] + delta)
    leftover = n - sum(by_kind.values())
    if leftover != 0:
        by_kind["clean"] += leftover
    return by_kind


def _lines(pairs: Sequence[tuple[str, float]]) -> tuple[LineItem, ...]:
    return tuple(LineItem(description=name, amount=amount) for name, amount in pairs)


def _apply_kind(job: dict[str, Any], kind: str) -> dict[str, Any]:
    """Return sow / lines / amounts / notes / change_order for a planted kind."""
    approved = float(job["approved"])
    lines = list(job["lines"])
    sow = job["sow"]
    notes = job["notes"]
    change_order = None
    extra = 0.0

    if kind == "clean":
        final = approved
    elif kind == "overbill":
        extra = round(approved * 0.14, 2)
        lines = [*lines, ("Rush weekend surcharge", extra)]
        final = round(approved + extra, 2)
        notes = (
            "Weekend surcharge added after the kickoff call. "
            "No change order on file."
        )
    elif kind == "underbill":
        dropped = lines[-1]
        lines = lines[:-1]
        final = round(sum(amount for _, amount in lines), 2)
        notes = (
            f"{dropped[0]} was quoted on the PO at ${dropped[1]:,.2f} but does "
            "not appear on this invoice. No credit memo is attached."
        )
    elif kind == "missing_scope":
        # Keep the dollar total; swap the last deliverable for a substitute.
        last_name, last_amt = lines[-1]
        lines = [*lines[:-1], ("Usage license (substituted)", last_amt)]
        final = approved
        notes = (
            f"{last_name} was not delivered. A usage license was billed at the "
            "same price without a written substitution approval."
        )
    elif kind == "extra_scope":
        extra = round(min(1800.0, approved * 0.12), 2)
        lines = [*lines, ("Off-scope courier / weekend labor", extra)]
        final = round(approved + extra, 2)
        notes = (
            "Courier and weekend labor were billed. They are not in the SOW "
            "and no change order authorizes them."
        )
    elif kind == "change_order":
        extra = 1500.0
        lines = [*lines, ("Change order — two extra interview / field days", extra)]
        final = round(approved + extra, 2)
        change_order = (
            "CO-14: add two extra on-site days at $750 each. "
            "Approved in writing by A. Chen on 12 Aug 2026."
        )
        notes = (
            "Extra days were worked 13–14 Aug. Change order CO-14 is on file "
            "and matches the billed delta."
        )
    elif kind == "ambiguous":
        extra = 150.0
        lines = [*lines, ("Materials variance", extra)]
        final = round(approved + extra, 2)
        notes = (
            "Small materials variance. Client verbally okayed it on a call; "
            "email confirmation is still outstanding."
        )
    else:
        raise ValueError(f"unknown planted kind: {kind}")

    return {
        "sow": sow,
        "lines": tuple(lines),
        "approved": approved,
        "final": final,
        "notes": notes,
        "change_order": change_order,
    }


def generate_invoices(
    n: int = DEFAULT_INVOICE_COUNT,
    *,
    seed: int = 7,
) -> list[Invoice]:
    """Build a deterministic batch with planted amount and scope defects."""
    mix = mix_for_count(n)
    invoices: list[Invoice] = []
    seq = 0
    job_index = 0
    for kind in PLANTED_KINDS:
        for _ in range(mix.get(kind, 0)):
            job = _JOBS[job_index % len(_JOBS)]
            planted = _apply_kind(job, kind)
            seq += 1
            job_index += 1
            invoice_number = f"INV-{2000 + seq}"
            invoices.append(
                Invoice(
                    id=f"inv-{seq:04d}",
                    vendor=job["vendor"],
                    invoice_number=invoice_number,
                    po_number=f"PO-{8800 + seq}",
                    service=job["service"],
                    sow=planted["sow"],
                    line_items=_lines(planted["lines"]),
                    approved_amount=planted["approved"],
                    final_amount=planted["final"],
                    delivery_notes=planted["notes"],
                    change_order=planted["change_order"],
                    planted_kind=kind,
                )
            )
    rng = random.Random(seed)
    rng.shuffle(invoices)
    return invoices


def invoice_state(invoice: Invoice) -> dict[str, Any]:
    """Structured state for a System One call. Omits planted labels."""
    return {
        "invoice_number": invoice.invoice_number,
        "vendor": invoice.vendor,
        "purchase_order": invoice.po_number,
        "service": invoice.service,
        "approved_amount_usd": invoice.approved_amount,
        "final_amount_usd": invoice.final_amount,
        "line_item_sum_usd": invoice.line_item_sum,
        "line_items": [asdict(item) for item in invoice.line_items],
        "statement_of_work": invoice.sow,
        "delivery_notes": invoice.delivery_notes,
        "change_order": invoice.change_order,
    }


def public_invoice(invoice: Invoice) -> dict[str, Any]:
    """Browser-facing invoice row. No planted labels."""
    return {
        "id": invoice.id,
        "vendor": invoice.vendor,
        "invoice_number": invoice.invoice_number,
        "po_number": invoice.po_number,
        "service": invoice.service,
        "sow": invoice.sow,
        "line_items": [asdict(item) for item in invoice.line_items],
        "approved_amount": invoice.approved_amount,
        "final_amount": invoice.final_amount,
        "delivery_notes": invoice.delivery_notes,
        "change_order": invoice.change_order,
    }


def jev_questions() -> dict[str, dict[str, Any]]:
    """Return a copy of the typed questions sent with every invoice."""
    return {key: dict(value) for key, value in JEV_QUESTIONS.items()}


def _noul_value(answer: Any) -> float:
    if hasattr(answer, "noul"):
        return float(answer.noul)
    if isinstance(answer, dict) and "noul" in answer:
        return float(answer["noul"])
    raise TypeError(f"cannot read noul from {type(answer)!r}")


def nouls_from_response(response: Any) -> tuple[float, float]:
    """Pull amount_matches and scope_covered noul values from a Jev response."""
    nouls = getattr(response, "nouls", None)
    if nouls is None and isinstance(response, dict):
        nouls = response.get("nouls") or response.get("answers")
    if nouls is None:
        raise TypeError("response has no nouls or answers")
    return _noul_value(nouls["amount_matches"]), _noul_value(nouls["scope_covered"])


def simulated_response(planted_kind: str) -> dict[str, Any]:
    """SDK-shaped answers for local preview. Never used when a live key is set."""
    amount, scope = SIMULATED_NOULS[planted_kind]
    return {
        "nouls": {
            "amount_matches": {"type": "noul", "noul": amount},
            "scope_covered": {"type": "noul", "noul": scope},
        }
    }


def compose_from_response(response: Any) -> dict[str, Any]:
    amount_noul, scope_noul = nouls_from_response(response)
    return compose_result(amount_noul, scope_noul)


AskFn = Callable[[dict[str, Any], dict[str, dict[str, Any]]], Awaitable[Any]]


async def run_evaluations(
    invoices: Sequence[Invoice],
    ask: AskFn,
    *,
    concurrency: int = 12,
    before_ask: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Fan out `ask` over invoices. Yields a result dict as each call finishes."""
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    sem = asyncio.Semaphore(concurrency)

    async def one(index: int, invoice: Invoice) -> dict[str, Any]:
        async with sem:
            if before_ask is not None:
                await before_ask()
            started = time.perf_counter()
            try:
                response = await ask(invoice_state(invoice), jev_questions())
                composed = compose_from_response(response)
                return {
                    "index": index,
                    "id": invoice.id,
                    "ok": True,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    **composed,
                }
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — surface to the demo stream
                return {
                    "index": index,
                    "id": invoice.id,
                    "ok": False,
                    "error": str(exc),
                    "latency_ms": (time.perf_counter() - started) * 1000,
                }

    tasks = [asyncio.create_task(one(index, invoice)) for index, invoice in enumerate(invoices)]
    try:
        for task in asyncio.as_completed(tasks):
            yield await task
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
