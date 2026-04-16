import { useState, useEffect } from "react";
import PipelineWalkthrough from "./PipelineWalkthrough";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:5000";

export default function PipelineView({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!propertyId) return;

    async function fetchData() {
      setLoading(true);
      setError("");
      setData(null);
      try {
        const res = await fetch(`${API_BASE_URL}/api/manager/overview/${propertyId}`);
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || "Failed to load pipeline data.");
        setData(json);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [propertyId]);

  return (
    <main className="page-content page-content--wide">
      {loading && (
        <div className="manager-state-card">
          <div className="section-kicker">Loading</div>
          <p className="manager-state-card__text">Fetching pipeline data…</p>
        </div>
      )}

      {error && !loading && (
        <div className="manager-state-card manager-state-card--error">
          <div className="section-kicker">Error</div>
          <p className="manager-state-card__text">{error}</p>
        </div>
      )}

      {data && !loading && (
        <>
          <PipelineWalkthrough pipeline={data.pipeline} propertyId={propertyId} />
        </>
      )}
    </main>
  );
}
