import { useState } from "react";

const STAR_LABELS = ["", "Terrible", "Poor", "Okay", "Good", "Excellent"];
const TRAVEL_TYPES = ["Solo", "Couple", "Family", "Business", "Group"];

export default function OverallRating({
  label,
  value,
  onChange,
  travelType,
  onTravelTypeChange,
  children,
}) {
  const [hovered, setHovered] = useState(0);
  const display = hovered || value;

  return (
    <section className="review-card">
      <div className="section-kicker">Overall</div>
      <h2 className="section-title section-title--compact">{label}</h2>

      <div className="stars-row">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            className={`star-button ${display >= star ? "is-active" : ""}`}
            onClick={() => onChange(star)}
            onMouseEnter={() => setHovered(star)}
            onMouseLeave={() => setHovered(0)}
            aria-label={`Rate ${star} star${star > 1 ? "s" : ""}`}
          >
            ★
          </button>
        ))}
      </div>

      <div className="stars-caption">
        {display ? STAR_LABELS[display] : "Tap to rate"}
      </div>

      <div className="travel-block">
        <div className="travel-label">How did you travel?</div>
        <div className="chip-group">
          {TRAVEL_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              className={`chip-button ${travelType === type ? "is-selected" : ""}`}
              onClick={() => onTravelTypeChange(type)}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {children}
    </section>
  );
}