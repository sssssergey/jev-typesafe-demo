import DecisionRail from "./components/DecisionRail.jsx";
import Header from "./components/Header.jsx";
import InvoiceTable from "./components/InvoiceTable.jsx";
import { useDemo } from "./useDemo.js";

export default function App() {
  const demo = useDemo();

  return (
    <div className="app">
      <Header
        runStatus={demo.runStatus}
        hasKey={demo.hasKey}
        simulate={demo.simulate}
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
          selectedId={demo.selectedId}
          currentId={demo.currentId}
          bars={demo.bars}
          throughput={demo.throughput}
        />
      </main>
    </div>
  );
}
