const SENTIMENT_COLOR = (score) => {
  if (score === null || score === undefined) return "#98a2b3";
  if (score >= 0.3) return "#12b76a";
  if (score >= 0) return "#f79009";
  return "#f04438";
};

function SentimentBar({ score }) {
  if (score === null || score === undefined) return null;
  // Map -1..1 to 0..100%, diverging from center (50%)
  const pct = ((score + 1) / 2) * 100;
  const mid = 50;
  const left = `${Math.min(pct, mid)}%`;
  const width = `${Math.abs(pct - mid)}%`;
  const color = SENTIMENT_COLOR(score);
  return (
    <div className="sentiment-bar">
      <div className="sentiment-bar__center" />
      <div className="sentiment-bar__fill" style={{ left, width, background: color }} />
    </div>
  );
}

function AmenityCard({ am, variant }) {
  return (
    <div className={`amenity-card amenity-card--${variant}`}>
      <div className="amenity-card__top">
        <span className="amenity-card__name">{am.amenity}</span>
        {variant === "good" ? (
          <span className="amenity-card__score" style={{ color: SENTIMENT_COLOR(am.avg_sentiment) }}>
            {am.avg_sentiment >= 0 ? "+" : ""}
            {am.avg_sentiment}
          </span>
        ) : (
          <span className="amenity-card__ask-score">ask {am.ask_score}</span>
        )}
      </div>

      <SentimentBar score={am.avg_sentiment} />

      {variant === "good" && (
        <div className="amenity-card__meta">{am.num_mentions} mentions</div>
      )}

      {variant === "warn" && am.ask_reason && (
        <div className="amenity-card__reason">{am.ask_reason}</div>
      )}

      {variant === "good" &&
        am.positive_reasons.slice(0, 2).map((r, i) => (
          <div key={i} className="amenity-card__quote amenity-card__quote--pos">
            &ldquo;{r}&rdquo;
          </div>
        ))}

      {variant === "warn" &&
        am.negative_reasons.slice(0, 2).map((r, i) => (
          <div key={i} className="amenity-card__quote amenity-card__quote--neg">
            &ldquo;{r}&rdquo;
          </div>
        ))}

      {variant === "warn" && am.avg_sentiment !== null && (
        <div
          className="amenity-card__meta"
          style={{ color: SENTIMENT_COLOR(am.avg_sentiment), marginTop: 6 }}
        >
          avg sentiment: {am.avg_sentiment >= 0 ? "+" : ""}
          {am.avg_sentiment}
        </div>
      )}
    </div>
  );
}

export default function PropertyOverview({ data }) {
  return (
    <div className="overview-section">
      <div className="overview-stats">
        <div className="overview-stat">
          <div className="overview-stat__value">{data.review_count}</div>
          <div className="overview-stat__label">Reviews</div>
        </div>
        <div className="overview-stat">
          <div className="overview-stat__value">{data.amenity_count}</div>
          <div className="overview-stat__label">Amenities tracked</div>
        </div>
        <div className="overview-stat">
          <div className="overview-stat__value">
            {data.best_amenities.length > 0 ? data.best_amenities[0].amenity : "—"}
          </div>
          <div className="overview-stat__label">Top positive</div>
        </div>
        <div className="overview-stat">
          <div className="overview-stat__value">
            {data.needs_attention.length > 0 ? data.needs_attention[0].amenity : "—"}
          </div>
          <div className="overview-stat__label">Top ask</div>
        </div>
      </div>

      <div className="overview-columns">
        <div className="overview-col">
          <div className="overview-col__header">
            <span className="overview-col__badge overview-col__badge--good">Performing well</span>
          </div>
          {data.best_amenities.length === 0 ? (
            <p className="overview-empty">No strongly positive amenities yet.</p>
          ) : (
            data.best_amenities.map((am) => (
              <AmenityCard key={am.amenity} am={am} variant="good" />
            ))
          )}
        </div>

        <div className="overview-col">
          <div className="overview-col__header">
            <span className="overview-col__badge overview-col__badge--warn">Needs attention</span>
          </div>
          {data.needs_attention.length === 0 ? (
            <p className="overview-empty">All amenities are well-documented.</p>
          ) : (
            data.needs_attention.map((am) => (
              <AmenityCard key={am.amenity} am={am} variant="warn" />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
