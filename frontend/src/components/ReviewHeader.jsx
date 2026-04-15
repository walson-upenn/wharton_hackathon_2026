export default function ReviewHeader({ properties = [], selectedPropertyId = "", onPropertyChange }) {
  return (
    <header className="review-header">
      <div className="review-header__inner">
        <div className="review-header__brand">
          <div className="review-header__logoBox">
            <div className="review-header__arrow" />
          </div>
          <span className="review-header__logoText">Expedia</span>
        </div>

        {properties.length > 0 && onPropertyChange && (
          <label className="review-header__picker">
            <span className="review-header__picker-label">Property</span>
            <select
              value={selectedPropertyId}
              onChange={(e) => onPropertyChange(e.target.value)}
            >
              {properties.map((p) => (
                <option key={p.property_id} value={p.property_id}>
                  {p.name || p.city || "Hotel"}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </header>
  );
}
