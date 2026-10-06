"use client";

export default function HrPanel({ alerts }: { alerts: string[] }) {
  return (
    <article>
      <h3>RRHH</h3>
      {alerts.length ? (
        <ul>{alerts.map((alert) => <li key={alert}>{alert}</li>)}</ul>
      ) : <p>Sin alertas de RRHH.</p>}
    </article>
  );
}