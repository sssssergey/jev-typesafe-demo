import { useCallback, useEffect, useRef, useState } from "react";
import { emptyBars, emptyThroughput } from "./format.js";

const PREVIEW_BANNER =
  "Preview mode: answers are local stand-ins for planted cases. Add TYPESAFE_API_KEY to .env and restart for live Jev. The key stays on the server.";

function applyResult(invoices, event) {
  return invoices.map((inv) => {
    if (inv.id !== event.id) {
      return inv.current ? { ...inv, current: false } : inv;
    }
    if (event.ok) {
      return {
        ...inv,
        current: true,
        amount_matches: event.amount_matches,
        scope_covered: event.scope_covered,
        latency_ms: event.latency_ms,
      };
    }
    return {
      ...inv,
      current: true,
      amount_matches: { verdict: "fail", noul: 0 },
      scope_covered: { verdict: "fail", noul: 0 },
    };
  });
}

export function useDemo() {
  const [invoices, setInvoices] = useState([]);
  const [runStatus, setRunStatus] = useState("idle");
  const [hasKey, setHasKey] = useState(false);
  const [simulate, setSimulate] = useState(true);
  const [banner, setBanner] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [currentId, setCurrentId] = useState(null);
  const [bars, setBars] = useState(emptyBars());
  const [throughput, setThroughput] = useState(emptyThroughput());
  const followRef = useRef(true);

  const setProgress = useCallback((event) => {
    setThroughput({
      done: event.done ?? 0,
      total: event.total ?? 0,
      perSec: event.per_sec ?? 0,
      elapsedMs: event.elapsed_ms ?? 0,
    });
    if (event.bars) setBars(event.bars);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetch("/api/status").then((r) => r.json());
        if (cancelled) return;
        setHasKey(Boolean(status.has_key));
        setSimulate(Boolean(status.simulate));
        setRunStatus(status.run.status);
        setProgress(status.run);
        setBanner(status.has_key && !status.simulate ? "" : PREVIEW_BANNER);
        const payload = await fetch("/api/invoices").then((r) => r.json());
        if (cancelled) return;
        setInvoices(payload.invoices);
      } catch (err) {
        if (!cancelled) setBanner(String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setProgress]);

  useEffect(() => {
    const stream = new EventSource("/api/stream");
    stream.onmessage = (msg) => {
      const event = JSON.parse(msg.data);
      if (event.type === "hello") {
        setRunStatus("running");
        setProgress({ done: 0, total: event.total, per_sec: 0, elapsed_ms: 0, bars: emptyBars() });
      } else if (event.type === "result") {
        setInvoices((prev) => applyResult(prev, event));
        setCurrentId(event.id);
        setProgress(event);
      } else if (event.type === "status" || event.type === "done") {
        setRunStatus(event.type === "done" ? "done" : event.status);
        setProgress(event);
      } else if (event.type === "error") {
        setBanner(event.error);
        setRunStatus("error");
      }
    };
    return () => stream.close();
  }, [setProgress]);

  const start = useCallback(async () => {
    followRef.current = true;
    setInvoices((prev) =>
      prev.map((inv) => {
        const next = { ...inv, current: false };
        delete next.amount_matches;
        delete next.scope_covered;
        delete next.latency_ms;
        return next;
      }),
    );
    setCurrentId(null);
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ concurrency: 12 }),
    });
    const body = await res.json();
    if (!body.ok) {
      setBanner(body.error || "Could not start the run");
      return;
    }
    setBanner(hasKey && !simulate ? "" : PREVIEW_BANNER);
    setRunStatus("running");
  }, [hasKey, simulate]);

  const togglePause = useCallback(async () => {
    const path = runStatus === "paused" ? "/api/resume" : "/api/pause";
    const body = await fetch(path, { method: "POST" }).then((r) => r.json());
    if (!body.ok) {
      setBanner(body.error || "Could not change run state");
      return;
    }
    setRunStatus(body.status);
  }, [runStatus]);

  const selectInvoice = useCallback((id) => {
    followRef.current = false;
    setSelectedId(id);
  }, []);

  const stopFollowing = useCallback(() => {
    followRef.current = false;
  }, []);

  return {
    invoices,
    runStatus,
    hasKey,
    simulate,
    banner,
    selectedId,
    currentId,
    bars,
    throughput,
    followRef,
    start,
    togglePause,
    selectInvoice,
    stopFollowing,
  };
}
