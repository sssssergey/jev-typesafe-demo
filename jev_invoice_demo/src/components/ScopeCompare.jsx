import { money } from "../format.js";

// Pair PO lines with invoice lines by description so each side can flag
// what the other lacks. Amounts are compared only for lines on both sides.
function diffLines(approved, delivered) {
  const byDesc = (items) => new Map(items.map((item) => [item.description, item]));
  const approvedMap = byDesc(approved);
  const deliveredMap = byDesc(delivered);
  const status = (item, other) => {
    const twin = other.get(item.description);
    if (!twin) return "only";
    return Math.abs(twin.amount - item.amount) < 0.005 ? "same" : "changed";
  };
  return {
    approved: approved.map((item) => ({ ...item, status: status(item, deliveredMap) })),
    delivered: delivered.map((item) => ({ ...item, status: status(item, approvedMap) })),
  };
}

function Column({ title, tone, note, noteLabel, lines, onlyLabel, total }) {
  return (
    <div className={`scope-col ${tone}`}>
      <h4>{title}</h4>
      <p className="scope-note">
        <b>{noteLabel}</b> {note}
      </p>
      <ul className="scope-lines">
        {lines.map((item) => (
          <li key={item.description} className={`scope-line ${item.status}`}>
            <span className="scope-desc">{item.description}</span>
            <span className="scope-amt">{money(item.amount)}</span>
            {item.status === "only" ? <em className="scope-flag">{onlyLabel}</em> : null}
            {item.status === "changed" ? <em className="scope-flag">amount differs</em> : null}
          </li>
        ))}
      </ul>
      <p className="scope-total">
        <span>Total</span>
        <b>{money(total)}</b>
      </p>
    </div>
  );
}

export default function ScopeCompare({ invoice }) {
  const { approved, delivered } = diffLines(invoice.approved_line_items || [], invoice.line_items || []);
  const missing = approved.filter((l) => l.status === "only").length;
  const added = delivered.filter((l) => l.status === "only").length;
  const scopeVerdict = invoice.scope_covered?.verdict;

  let summary = "Billed lines match the purchase order line for line.";
  if (missing || added) {
    const parts = [];
    if (missing) parts.push(`${missing} approved line${missing > 1 ? "s" : ""} not billed`);
    if (added) parts.push(`${added} billed line${added > 1 ? "s" : ""} not on the PO`);
    summary = parts.join(" · ");
  }

  return (
    <div className={`scope ${scopeVerdict || ""}`}>
      <div className="scope-summary">
        <span>{summary}</span>
        {scopeVerdict ? <span className={`chip ${scopeVerdict}`}>scope {scopeVerdict}</span> : null}
      </div>
      <div className="scope-grid">
        <Column
          title="Approved scope"
          tone="approved"
          noteLabel="SOW."
          note={invoice.sow}
          lines={approved}
          onlyLabel="not delivered"
          total={invoice.approved_amount}
        />
        <Column
          title="Delivered / billed"
          tone="delivered"
          noteLabel="Delivery notes."
          note={invoice.delivery_notes}
          lines={delivered}
          onlyLabel="not in SOW"
          total={invoice.final_amount}
        />
      </div>
      {invoice.change_order ? (
        <p className="scope-co">
          <b>Change order on file.</b> {invoice.change_order}
        </p>
      ) : null}
    </div>
  );
}
