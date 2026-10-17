"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { buildBrasalandSnapshot, type BrasalandBusinessInput } from "@repo/shared-types";

const SupplierPanel = dynamic(() => import("./SupplierPanel"), {
  loading: () => <p role="status">Cargando proveedores...</p>,
});
const HrPanel = dynamic(() => import("./HrPanel"), {
  loading: () => <p role="status">Cargando RRHH...</p>,
});

const views = [
  { id: "stock", label: "Stock" },
  { id: "suppliers", label: "Proveedores" },
  { id: "hr", label: "RRHH" },
] as const;

export default function Dashboard({ input }: { input: BrasalandBusinessInput }) {
  const [view, setView] = useState<(typeof views)[number]["id"]>("stock");
  const snapshot = useMemo(() => buildBrasalandSnapshot(input), [input]);

  return (
    <div className="backoffice-shell">
      <aside className="sidebar">
        <p className="chip">Backoffice</p>
        <h1>Brasaland Control Center</h1>
        <p>Vista de entrada para operaciones, compras y direccion ejecutiva.</p>
      </aside>
      <main className="main-panel">
        <section className="panel">
          <h2>Resumen semanal ({snapshot.weekLabel})</h2>
          <div className="grid two">
            {snapshot.marketSummary.map((market) => (
              <article key={market.country} className="metric">
                <p>{market.country === "CO" ? "Colombia" : "Florida"} · {market.currency}</p>
                <strong>{market.revenue.toLocaleString("es-CO", { maximumFractionDigits: 2 })}</strong>
                <span>{market.orders} pedidos · ticket prom. {market.averageTicket.toLocaleString("es-CO")}</span>
              </article>
            ))}
          </div>
          {snapshot.topTicketStore && (
            <p className="note">
              Ticket mas alto del periodo: {snapshot.topTicketStore.storeName} ({snapshot.topTicketStore.averageTicket.toLocaleString("es-CO")} {snapshot.topTicketStore.currency})
            </p>
          )}
        </section>
        <section className="panel">
          <h2>Alertas operativas y de gestion</h2>
          <div className="view-tabs" role="group" aria-label="Area de gestion">
            {views.map((item) => (
              <button key={item.id} type="button" aria-pressed={view === item.id}
                aria-controls="management-view" onClick={() => setView(item.id)}>
                {item.label}
              </button>
            ))}
          </div>
          <div id="management-view" className="management-view" aria-live="polite">
            {view === "stock" && (
              <article>
                <h3>Stock</h3>
                {snapshot.stockRiskAlerts.length ? (
                  <ul>{snapshot.stockRiskAlerts.map((alert) => <li key={alert}>{alert}</li>)}</ul>
                ) : <p>Sin alertas de stock.</p>}
              </article>
            )}
            {view === "suppliers" && <SupplierPanel alerts={snapshot.supplierAlerts} />}
            {view === "hr" && <HrPanel alerts={snapshot.hrAlerts} />}
          </div>
        </section>
      </main>
    </div>
  );
}