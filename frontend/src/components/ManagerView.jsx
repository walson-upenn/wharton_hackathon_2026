import { useState, useEffect } from "react";
import PropertyOverview from "./PropertyOverview";
import PipelineWalkthrough from "./PipelineWalkthrough";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:5000";

export default function ManagerView({ propertyId, properties, onPropertyChange }) {
  const [tab, setTab] = useState("overview");
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
        if (!res.ok) throw new Error(json.error || "Failed to load manager data.");
        setData(json);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [propertyId]);

  const starStr = (rating) => {
    const n = parseInt(rating, 10);
    if (!n || n < 1) return "";
    return "★".repeat(Math.min(n, 5));
  };

  return (
    <main className="page-content">
      {properties.length > 0 && (
        <label className="property-picker">
          <span>Property</span>
          <select value={propertyId} onChange={(e) => onPropertyChange(e.target.value)}>
            {properties.map((p) => (
              <option key={p.property_id} value={p.property_id}>
                {p.name || p.city || "Hotel"}
              </option>
            ))}
          </select>
        </label>
      )}

      {loading && (
        <div className="manager-state-card">
          <div className="section-kicker">Loading</div>
          <p className="manager-state-card__text">Fetching property data…</p>
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
          <div className="manager-hero">
            <div className="manager-hero__info">
              <div className="manager-hero__location">{data.property.location}</div>
              <h1 className="manager-hero__name">{data.property.name}</h1>
              {data.property.starRating && (
                <div className="manager-hero__stars">{starStr(data.property.starRating)}</div>
              )}
              {data.property.description && (
                <p className="manager-hero__desc">{data.property.description}</p>
              )}
            </div>
          </div>

          <div className="manager-tabs">
            <button
              className={`manager-tab ${tab === "overview" ? "is-active" : ""}`}
              onClick={() => setTab("overview")}
            >
              Overview
            </button>
            <button
              className={`manager-tab ${tab === "pipeline" ? "is-active" : ""}`}
              onClick={() => setTab("pipeline")}
            >
              Pipeline walkthrough
            </button>
          </div>

          {tab === "overview" && <PropertyOverview data={data.overview} />}
          {tab === "pipeline" && <PipelineWalkthrough pipeline={data.pipeline} propertyId={propertyId} />}
        </>
      )}
    </main>
  );
}
