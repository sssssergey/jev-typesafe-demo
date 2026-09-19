import { money } from "../format.js";

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

export default function DecisionRail({ invoices, selectedId, currentId, bars, throughput }) {
  const selected = invoices.find((inv) => inv.id === selectedId);
  const current = invoices.find((inv) => inv.id === currentId);

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
        <div className="box">
          <b>{(throughput.perSec || 0).toFixed(1)} /s</b>
          <span>{((throughput.elapsedMs || 0) / 1000).toFixed(1)}s elapsed</span>
        </div>
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

      <h2>Selected invoice</h2>
      <div className="detail">
        {selected ? (
          <>
            <h3>
              {selected.invoice_number} · {selected.vendor}
            </h3>
            <p>{selected.sow}</p>
            {selected.change_order ? (
              <p>
                <b>Change order.</b> {selected.change_order}
              </p>
            ) : null}
            <p>{selected.delivery_notes}</p>
            <ul>
              {(selected.line_items || []).map((item) => (
                <li key={item.description}>
                  {item.description} — {money(item.amount)}
                </li>
              ))}
            </ul>
            <p>
              Approved {money(selected.approved_amount)} · final {money(selected.final_amount)}
            </p>
          </>
        ) : (
          <p>Click a row to read the SOW, lines, and delivery notes Jev sees.</p>
        )}
      </div>
    </aside>
  );
}
