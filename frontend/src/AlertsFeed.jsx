import { useEffect, useState } from "react";

export default function AlertsFeed() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const url = import.meta.env.VITE_API_BASE_URL + "/api/stream/alerts";
    const src = new EventSource(url);

    const onAlert = (e) => {
      const alert = JSON.parse(e.data);
      setAlerts((prev) => [alert, ...prev].slice(0, 50)); // keep last 50 alerts
    };

    src.addEventListener("alert", onAlert);
    return () => src.close();
  }, []);

  return (
    <div style={{ marginTop: 24 }}>
      <h2>📡 Live Alerts</h2>
      {alerts.length === 0 && <p>No alerts yet...</p>}
      <ul>
        {alerts.map((a, i) => (
          <li key={i}>
            <code>{a.risk_level ?? "?"}</code> — {(a.reasons || []).join(", ")}{" "}
            (score: {a.final_risk ?? "?"})
          </li>
        ))}
      </ul>
    </div>
  );
}
