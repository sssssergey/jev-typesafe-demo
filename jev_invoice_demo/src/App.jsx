import DecisionRail from "./components/DecisionRail.jsx";
import Header from "./components/Header.jsx";
import InvoiceDialog from "./components/InvoiceDialog.jsx";
import InvoiceTable from "./components/InvoiceTable.jsx";
import { useDemo } from "./useDemo.js";
import { useTheme } from "./useTheme.js";

export default function App() {
  const demo = useDemo();
  const { theme, toggle: toggleTheme } = useTheme();
  const selected = demo.invoices.find((inv) => inv.id === demo.selectedId) || null;

  return (
    <div className="app">
      <Header
        runStatus={demo.runStatus}
        hasKey={demo.hasKey}
        simulate={demo.simulate}
        theme={theme}
        onToggleTheme={toggleTheme}
        onStart={demo.start}
        onTogglePause={demo.togglePause}
      />
      <div className="banner">{demo.banner}</div>
      <main>
        <InvoiceTable
          invoices={demo.invoices}
          selectedId={demo.selectedId}
          currentId={demo.currentId}
          followRef={demo.followRef}
          onSelect={demo.selectInvoice}
          onScroll={demo.stopFollowing}
        />
        <DecisionRail
          invoices={demo.invoices}
          currentId={demo.currentId}
          bars={demo.bars}
          throughput={demo.throughput}
          elapsedMs={demo.elapsedMs}
          runStatus={demo.runStatus}
          live={demo.hasKey && !demo.simulate}
        />
      </main>
      <InvoiceDialog invoice={selected} onClose={() => demo.selectInvoice(null)} />
    </div>
  );
}
