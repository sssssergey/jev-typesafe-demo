import { formatCost, formatDuration } from "../format.js";

function StackedBar({ counts }) {
  const total = counts.pass + counts.review + counts.fail;
  const pct = (n) => (total ? (n / total) * 100 : 0);
  return (
    <>
      <div className="bar">
        <i className="pass" style={{ width: `${pct(counts.pass)}%` }} />
        <i className="review" style={{ width: `${pct(counts.review)}%` }} />
        <i className="fail" style={{ width: `${pct(counts.fail)}%` }} />
      </div>
      <div className="legend">
        <span className="pass">
          pass <b>{counts.pass}</b>
        </span>
        <span className="review">
          review <b>{counts.review}</b>
        </span>
        <span className="fail">
          fail <b>{counts.fail}</b>
        </span>
      </div>
    </>
  );
}

function NoulTrack({ label, answer }) {
  const noul = answer?.noul ?? 0;
  const verdict = answer?.verdict || "";
  return (
    <div className="row">
      <span>{label}</span>
      <div className={`track ${verdict}`}>
        <span style={{ width: `${Math.max(0, Math.min(1, noul)) * 100}%` }} />
      </div>
      <b>{answer ? noul.toFixed(2) : "—"}</b>
    </div>
  );
}

function durationLabel(runStatus) {
  if (runStatus === "running") return "running";
  if (runStatus === "paused") return "paused";
  return "last run duration";
}

function CostCard({ usage, live, hasRun }) {
  const tokens = `${usage.inputTokens.toLocaleString("en-US")} input tokens`;
  if (!live) {
    return (
      <div className="box cost">
        <b>—</b>
        <span>preview mode, no Jev charge</span>
      </div>
    );
  }
  return (
    <div className="box cost">
      <b>{hasRun ? formatCost(usage.costUsd) : "—"}</b>
      <span>
        last run cost · {tokens}
        {usage.pricePerMtok ? ` @ $${usage.pricePerMtok}/M` : ""}
      </span>
    </div>
  );
}

export default function DecisionRail({
  invoices,
  currentId,
  bars,
  throughput,
  elapsedMs,
  runStatus,
  live,
}) {
  const current = invoices.find((inv) => inv.id === currentId);
  const hasRun = throughput.done > 0 || runStatus === "running";

  return (
    <aside className="rail">
      <h2>Throughput</h2>
      <div className="stat">
        <div className="box">
          <b>
            {throughput.done} / {throughput.total}
          </b>
          <span>invoices reviewed</span>
        </div>
        <div className={`box timer ${runStatus}`}>
          <b>{hasRun ? formatDuration(elapsedMs || 0) : "—"}</b>
          <span>{durationLabel(runStatus)}</span>
        </div>
        <div className="box">
          <b>{(throughput.perSec || 0).toFixed(1)} /s</b>
          <span>invoices per second</span>
        </div>
        <CostCard usage={throughput.usage} live={live} hasRun={hasRun} />
      </div>

      <h2>Amount match</h2>
      <StackedBar counts={bars.amount_matches} />
      <h2>Scope coverage</h2>
      <StackedBar counts={bars.scope_covered} />

      <h2>Current decision</h2>
      <div className="detail" style={{ marginBottom: 12 }}>
        {current?.amount_matches ? (
          <>
            <h3>
              {current.invoice_number} · {current.vendor}
            </h3>
            <p>
              {current.service}. {current.latency_ms ? `${current.latency_ms.toFixed(0)} ms` : ""}
            </p>
          </>
        ) : (
          <p>Start a run to watch Jev fill both Noul questions on each invoice.</p>
        )}
      </div>
      <div className="prob">
        <NoulTrack label="amount" answer={current?.amount_matches} />
        <NoulTrack label="scope" answer={current?.scope_covered} />
      </div>
      <p className="hint">Click a row to compare the approved scope with what was delivered and billed.</p>
    </aside>
  );
}
