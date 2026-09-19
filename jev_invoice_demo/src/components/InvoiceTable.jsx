import { useEffect, useRef } from "react";
import { money } from "../format.js";
import VerdictChip from "./VerdictChip.jsx";

export default function InvoiceTable({
  invoices,
  selectedId,
  currentId,
  followRef,
  onSelect,
  onScroll,
}) {
  const currentRow = useRef(null);

  useEffect(() => {
    if (followRef.current && currentRow.current) {
      currentRow.current.scrollIntoView({ block: "center" });
    }
  }, [currentId, followRef]);

  return (
    <section
      className="list"
      tabIndex={-1}
      onWheel={onScroll}
      onTouchMove={onScroll}
      onKeyDown={(e) => {
        if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(e.key)) onScroll();
      }}
    >
      <table>
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Vendor / scope</th>
            <th className="num">Approved</th>
            <th className="num">Final</th>
            <th className="num">Checks</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => {
            const delta = inv.final_amount - inv.approved_amount;
            const matched = Math.abs(delta) < 0.5;
            const deltaTxt = matched ? "match" : delta > 0 ? `+${money(delta)}` : money(delta);
            const active = inv.id === selectedId;
            const current = inv.id === currentId;
            return (
              <tr
                key={inv.id}
                ref={current ? currentRow : null}
                className={`${active ? "active" : ""} ${current ? "current" : ""}`.trim()}
                onClick={() => onSelect(inv.id)}
              >
                <td className="mono">
                  {inv.invoice_number}
                  <div className="svc">{inv.po_number}</div>
                </td>
                <td>
                  {inv.vendor}
                  <div className="svc">{inv.service}</div>
                </td>
                <td className="num mono">{money(inv.approved_amount)}</td>
                <td className="num mono">
                  {money(inv.final_amount)}
                  <div className={`delta ${matched ? "same" : "up"}`}>{deltaTxt}</div>
                </td>
                <td className="num">
                  <div className="checks">
                    <VerdictChip verdict={inv.amount_matches?.verdict} />
                    <VerdictChip verdict={inv.scope_covered?.verdict} />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
