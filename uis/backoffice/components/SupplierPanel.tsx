"use client";

export default function SupplierPanel({ alerts }: { alerts: string[] }) {
  return (
    <article>
      <h3>Proveedores</h3>
      {alerts.length ? (
        <ul>{alerts.map((alert) => <li key={alert}>{alert}</li>)}</ul>
      ) : <p>Sin alertas de proveedores.</p>}
    </article>
  );
}