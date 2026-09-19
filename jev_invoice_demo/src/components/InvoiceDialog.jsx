import { useEffect, useRef } from "react";
import ScopeCompare from "./ScopeCompare.jsx";
import VerdictChip from "./VerdictChip.jsx";

// Native <dialog> so Escape, focus trapping and the backdrop come for free.
export default function InvoiceDialog({ invoice, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    if (invoice && !el.open) el.showModal();
    if (!invoice && el.open) el.close();
    return undefined;
  }, [invoice]);

  if (!invoice) return null;

  const onBackdropClick = (event) => {
    if (event.target === ref.current) onClose();
  };

  return (
    <dialog ref={ref} className="invoice-dialog" onClose={onClose} onClick={onBackdropClick}>
      <div className="dialog-body detail">
        <div className="dialog-head">
          <div>
            <h3>
              {invoice.invoice_number} · {invoice.vendor}
            </h3>
            <p>
              {invoice.service} · {invoice.po_number}
            </p>
          </div>
          <div className="dialog-chips">
            {invoice.amount_matches ? (
              <span className="dialog-chip">
                amount <VerdictChip verdict={invoice.amount_matches.verdict} />
              </span>
            ) : null}
            {invoice.scope_covered ? (
              <span className="dialog-chip">
                scope <VerdictChip verdict={invoice.scope_covered.verdict} />
              </span>
            ) : null}
            <button className="btn icon" type="button" onClick={onClose} aria-label="Close" title="Close">
              ×
            </button>
          </div>
        </div>
        <ScopeCompare invoice={invoice} />
      </div>
    </dialog>
  );
}
