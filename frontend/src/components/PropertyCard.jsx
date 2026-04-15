export default function PropertyCard({ property }) {
  return (
    <section className="property-card">
      <div className="property-card__icon">🏨</div>
      <div>
        <div className="property-card__name">{property.name}</div>
        <div className="property-card__meta">{property.location}</div>
        <div className="property-card__pill">{property.stayRange}</div>
      </div>
    </section>
  );
}