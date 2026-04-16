import { useState } from "react";

const TIER_COLORS = {
  critical: "#b42318",
  important: "#f79009",
  moderate: "#3662d8",
  minor: "#98a2b3",
};

function TierBadge({ tier }) {
  return (
    <span
      className="tier-badge"
      style={{ background: TIER_COLORS[tier] + "18", color: TIER_COLORS[tier] }}
    >
      {tier}
    </span>
  );
}

function CritBar({ value }) {
  return (
    <div className="crit-bar">
      <div
        className="crit-bar__fill"
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

function SentimentChip({ score }) {
  if (score === null || score === undefined) return <span className="sentiment-chip sentiment-chip--neutral">—</span>;
  const label = score >= 0.3 ? "positive" : score <= -0.3 ? "negative" : "mixed";
  const cls = score >= 0.3 ? "pos" : score <= -0.3 ? "neg" : "neutral";
  return <span className={`sentiment-chip sentiment-chip--${cls}`}>{label}</span>;
}

function ComponentBar({ label, value, color }) {
  return (
    <div className="comp-bar-row">
      <span className="comp-bar-row__label">{label}</span>
      <div className="comp-bar-row__track">
        <div
          className="comp-bar-row__fill"
          style={{ width: `${Math.round(value * 100)}%`, background: color }}
        />
      </div>
      <span className="comp-bar-row__val">{value.toFixed(2)}</span>
    </div>
  );
}

function StepCard({ num, title, description, badge, children }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="pipeline-step">
      <div className="pipeline-step__rail">
        <div className="pipeline-step__circle">{num}</div>
      </div>
      <div className={`pipeline-step__card ${open ? "is-open" : "is-collapsed"}`}>
        <button className="pipeline-step__header" onClick={() => setOpen((o) => !o)}>
          <div className="pipeline-step__title-group">
            <span className="pipeline-step__title">{title}</span>
            <span className="pipeline-step__desc">{description}</span>
          </div>
          {badge && <span className="pipeline-step__badge">{badge}</span>}
          <span className="pipeline-step__chevron">{open ? "▲" : "▼"}</span>
        </button>
        {open && <div className="pipeline-step__body">{children}</div>}
      </div>
    </div>
  );
}

// ── Step 1: Amenity Pruning ────────────────────────────────────────────────

const STATUS_LABEL = {
  kept: "kept",
  normalized: "normalized",
  pruned: "pruned",
};

const STATUS_CLASS = {
  kept: "status-chip--in",
  normalized: "status-chip--norm",
  pruned: "status-chip--out",
};

function Step1({ step }) {
  const { entries, total_raw, pruned, normalized, kept } = step;
  return (
    <StepCard
      num={1}
      title="Amenity discovery & pruning"
      description="Raw amenity strings from the property listing are normalized and filtered before any scoring."
      badge={`${total_raw} raw → ${kept} canonical`}
    >
      <p className="pipeline-prose">
        Every property listing in our dataset contains dozens of raw amenity strings across
        multiple fields — some useful (<em>&ldquo;free wifi&rdquo;</em>), some redundant variants
        (<em>&ldquo;available in all rooms: free wifi&rdquo;</em>), and some too technical for
        a guest to ever mention in a review (<em>&ldquo;at least 80% lighting from leds&rdquo;</em>).
        We pass all strings through a GPT-built taxonomy that either prunes them or maps them to
        a clean canonical label. Duplicates that collapse to the same canonical name are merged.
      </p>

      <div className="pipeline-summary-row">
        <div className="pipeline-summary-chip">
          <span className="pipeline-summary-chip__val">{total_raw}</span> raw strings
        </div>
        <span className="pipeline-summary-arrow">→</span>
        <div className="pipeline-summary-chip pipeline-summary-chip--green">
          <span className="pipeline-summary-chip__val">{kept}</span> canonical amenities
        </div>
        {pruned > 0 && (
          <div className="pipeline-summary-chip pipeline-summary-chip--gray">
            <span className="pipeline-summary-chip__val">{pruned}</span> pruned
          </div>
        )}
        {normalized > 0 && (
          <div className="pipeline-summary-chip pipeline-summary-chip--blue">
            <span className="pipeline-summary-chip__val">{normalized}</span> normalized
          </div>
        )}
      </div>

      <div className="pipeline-table-wrap">
        <table className="pipeline-table">
          <thead>
            <tr>
              <th>Raw string (from listing)</th>
              <th>Canonical name</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={i} className={e.status === "pruned" ? "pipeline-table__row--muted" : ""}>
                <td className="pipeline-table__raw">{e.raw}</td>
                <td>
                  {e.status === "pruned" ? (
                    <span className="pipeline-table__muted">—</span>
                  ) : (
                    <span className={e.status === "normalized" ? "pipeline-table__canon--changed" : ""}>
                      {e.canonical}
                    </span>
                  )}
                </td>
                <td>
                  <span className={`status-chip ${STATUS_CLASS[e.status]}`}>
                    {STATUS_LABEL[e.status]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </StepCard>
  );
}

// ── Step 2: Importance Ranking ─────────────────────────────────────────────

function Step2({ step }) {
  const { ranked_amenities } = step;
  return (
    <StepCard
      num={2}
      title="Amenity importance ranking"
      description="Rank surviving amenities by how much travelers care about them at this property."
      badge={`${ranked_amenities.length} amenities`}
    >
      <p className="pipeline-prose">
        Each amenity is assigned a <strong>criticality score</strong> (0–1) that reflects how
        commonly travelers mention and care about it for this property type. Higher criticality
        amplifies the final AskScore — an unresolved issue with a critical amenity is more urgent
        than the same issue with a minor one.
      </p>

      <div className="pipeline-rank-list">
        {ranked_amenities.map((am, i) => (
          <div key={am.amenity} className="rank-row">
            <span className="rank-row__index">{i + 1}</span>
            <span className="rank-row__name">{am.amenity}</span>
            <div className="rank-row__bar-wrap">
              <div
                className="rank-row__bar"
                style={{ width: `${Math.round(am.criticality * 100)}%` }}
              />
            </div>
            <span className="rank-row__val">{am.criticality.toFixed(2)}</span>
            <TierBadge tier={am.tier} />
          </div>
        ))}
      </div>
    </StepCard>
  );
}

// ── Per-Review pipeline diagram ────────────────────────────────────────────

function ReviewPipelineDiagram() {
  return (
    <div className="rpd">
      <div className="rpd-node rpd-node--purple">
        <div className="rpd-node__num">1</div>
        <div className="rpd-node__title">Mention Detection</div>
        <p className="rpd-node__desc">
          Which of this property&rsquo;s amenities does the reviewer actually reference?
        </p>
        <span className="rpd-chip rpd-chip--purple">amenity list</span>
      </div>

      <div className="rpd-arrow">→</div>

      <div className="rpd-parallel">
        <div className="rpd-parallel__label">↑ PARALLEL</div>
        <div className="rpd-node rpd-node--teal">
          <div className="rpd-node__num">2a</div>
          <div className="rpd-node__title">Sentiment Scoring</div>
          <p className="rpd-node__desc">
            Valence (pos&nbsp;/&nbsp;neg&nbsp;/&nbsp;neu) + intensity (strong&nbsp;/&nbsp;weak)
            &rarr; score in [&minus;1,&nbsp;1]
          </p>
          <span className="rpd-chip rpd-chip--teal">sentiment</span>
        </div>
        <div className="rpd-node rpd-node--teal">
          <div className="rpd-node__num">2b</div>
          <div className="rpd-node__title">Detail Scoring</div>
          <p className="rpd-node__desc">
            4 binary criteria: mentioned &rarr; specific &rarr; multiple attributes
            &rarr; rich context&nbsp;= [0,&nbsp;4]
          </p>
          <span className="rpd-chip rpd-chip--teal">detail depth</span>
        </div>
      </div>

      <div className="rpd-arrow">→</div>

      <div className="rpd-conditional">
        <div className="rpd-conditional__label">IF NON-NEUTRAL</div>
        <div className="rpd-node rpd-node--amber">
          <div className="rpd-node__num">3</div>
          <div className="rpd-node__title">Reason Extraction</div>
          <p className="rpd-node__desc">
            Extracts concrete, specific phrases explaining the sentiment&nbsp;&mdash;
            not vague adjectives
          </p>
          <span className="rpd-chip rpd-chip--amber">reason list</span>
        </div>
      </div>
    </div>
  );
}

// ── Step 3: Per-Review Analysis ────────────────────────────────────────────

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:5000";

const DETAIL_LABELS = ["none", "vague", "brief", "decent", "detailed"];

function ReviewSampleDisplay({ review }) {
  return (
    <>
      <div className="review-sample-card">
        <div className="review-sample-card__meta">
          {review.date && <span>{review.date}</span>}
          {review.title && (
            <>
              <span className="review-sample-card__dot">·</span>
              <span>&ldquo;{review.title}&rdquo;</span>
            </>
          )}
        </div>
        {review.text && (
          <p className="review-sample-card__text">
            {review.text}
          </p>
        )}
      </div>

      <div className="pipeline-table-wrap">
        <table className="pipeline-table">
          <thead>
            <tr>
              <th>Amenity</th>
              <th>Sentiment</th>
              <th>Detail</th>
              <th>Extracted reasons</th>
            </tr>
          </thead>
          <tbody>
            {review.amenities.map((am) => (
              <tr key={am.amenity}>
                <td>{am.amenity}</td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <SentimentChip score={am.sentiment} />
                    {am.sentiment !== null && (
                      <span className="pipeline-table__num">
                        {am.sentiment >= 0 ? "+" : ""}
                        {am.sentiment?.toFixed(2)}
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  <span className="detail-level">
                    {DETAIL_LABELS[Math.min(am.detail ?? 0, 4)]}
                    <span className="detail-level__num"> ({am.detail ?? 0}/4)</span>
                  </span>
                </td>
                <td className="pipeline-table__reasons">
                  {am.reasons.length > 0
                    ? am.reasons.map((r, i) => (
                        <span key={i} className="reason-chip">{r}</span>
                      ))
                    : <span className="pipeline-table__muted">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Step3({ step, propertyId }) {
  const { sample_review, total_reviews } = step;
  const [review, setReview] = useState(sample_review);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRefresh = async () => {
    const nextSkip = skip + 1;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/manager/review-sample/${propertyId}?skip=${nextSkip}`
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Could not load review.");
      setReview(json);
      setSkip(nextSkip);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!review) {
    return (
      <StepCard num={3} title="Per-review extraction" description="No review data available." />
    );
  }

  return (
    <StepCard
      num={3}
      title="Per-review analysis pipeline"
      description="Each review is parsed to extract amenity-level sentiment, detail depth, and key reasons."
      badge={`${total_reviews} reviews processed`}
    >
      <p className="pipeline-prose">
        Every review passes through an extraction pipeline that identifies which amenities are
        mentioned, assigns a <strong>sentiment</strong> score (−1 to +1), rates the{" "}
        <strong>detail depth</strong> (0–4), and pulls out the key reasons behind the rating.
      </p>

      <ReviewPipelineDiagram />

      <div className="review-sample-header">
        <span className="review-sample-header__count">
          Example {skip + 1} of {total_reviews}
        </span>
        <button
          className="review-refresh-btn"
          onClick={handleRefresh}
          disabled={loading}
        >
          {loading ? "Loading…" : "Next example →"}
        </button>
      </div>

      {error && <p className="review-sample-error">{error}</p>}

      <ReviewSampleDisplay review={review} />
    </StepCard>
  );
}

// ── Step 4: AskScore Computation ─────────────────────────────────────────

const COMP_COLORS = {
  knowledge_gap: "#3662d8",
  controversy: "#7b4fcc",
  decline: "#f79009",
  staleness: "#667085",
};

const COMP_WEIGHTS = { knowledge_gap: 0.40, controversy: 0.20, decline: 0.20, staleness: 0.15 };

function StackedScoreBar({ am, maxScore }) {
  const barWidth = maxScore > 0 ? (am.score / maxScore) * 100 : 0;
  const contribs = Object.fromEntries(
    Object.entries(COMP_WEIGHTS).map(([k, w]) => [k, am.criticality * w * (am.components[k] || 0)])
  );
  const total = Object.values(contribs).reduce((a, b) => a + b, 0);

  return (
    <div className="stacked-bar-row">
      <div className="stacked-bar">
        <div className="stacked-bar__fill" style={{ width: `${barWidth}%` }}>
          {total > 0 &&
            Object.entries(contribs).map(([k, v]) => (
              <div
                key={k}
                style={{ flex: v / total, background: COMP_COLORS[k], height: "100%" }}
                title={`${k}: ${v.toFixed(3)}`}
              />
            ))}
        </div>
      </div>
      <span className="stacked-bar__score">{am.score.toFixed(3)}</span>
    </div>
  );
}

function Step4({ step }) {
  const { scored_amenities } = step;
  const maxScore = scored_amenities[0]?.score || 1;

  return (
    <StepCard
      num={4}
      title="AskScore computation"
      description="Combine criticality and four signal components to rank which amenities to ask about next."
      badge={`top ${Math.min(scored_amenities.length, 10)} shown`}
    >
      <p className="pipeline-prose">
        The final AskScore weights four complementary signals, each scaled by the amenity&rsquo;s
        criticality:
      </p>

      <div className="formula-box">
        <code className="formula">
          score = criticality &times; (
          <span style={{ color: COMP_COLORS.knowledge_gap }}>0.40 &times; knowledge_gap</span>
          {" + "}
          <span style={{ color: COMP_COLORS.controversy }}>0.20 &times; controversy</span>
          {" + "}
          <span style={{ color: COMP_COLORS.decline }}>0.20 &times; decline</span>
          {" + "}
          <span style={{ color: COMP_COLORS.staleness }}>0.15 &times; staleness</span>
          )
        </code>
      </div>

      <div className="formula-legend">
        <div className="formula-legend__item">
          <span className="formula-legend__dot" style={{ background: COMP_COLORS.knowledge_gap }} />
          <strong>Knowledge gap</strong> — reviews mention the amenity without useful detail
        </div>
        <div className="formula-legend__item">
          <span className="formula-legend__dot" style={{ background: COMP_COLORS.controversy }} />
          <strong>Controversy</strong> — reviewers disagree (50/50 positive vs. negative)
        </div>
        <div className="formula-legend__item">
          <span className="formula-legend__dot" style={{ background: COMP_COLORS.decline }} />
          <strong>Decline</strong> — recent sentiment is worse than older reviews
        </div>
        <div className="formula-legend__item">
          <span className="formula-legend__dot" style={{ background: COMP_COLORS.staleness }} />
          <strong>Staleness</strong> — the amenity hasn&rsquo;t been mentioned recently
        </div>
      </div>

      <div className="score-list">
        {scored_amenities.slice(0, 10).map((am, i) => (
          <div key={am.amenity} className="score-row">
            <div className="score-row__header">
              <span className="score-row__rank">#{i + 1}</span>
              <span className="score-row__name">{am.amenity}</span>
              <TierBadge tier={am.tier} />
              <span className="score-row__mentions">
                {am.stats.num_mentions} mention{am.stats.num_mentions !== 1 ? "s" : ""}
              </span>
            </div>
            <StackedScoreBar am={am} maxScore={maxScore} />
            <div className="score-row__components">
              <ComponentBar label="knowledge gap" value={am.components.knowledge_gap} color={COMP_COLORS.knowledge_gap} />
              <ComponentBar label="controversy" value={am.components.controversy} color={COMP_COLORS.controversy} />
              <ComponentBar label="decline" value={am.components.decline} color={COMP_COLORS.decline} />
              <ComponentBar label="staleness" value={am.components.staleness} color={COMP_COLORS.staleness} />
            </div>
          </div>
        ))}
      </div>
    </StepCard>
  );
}

// ── Main export ────────────────────────────────────────────────────────────

export default function PipelineWalkthrough({ pipeline, propertyId }) {
  return (
    <div className="pipeline-section">
      <Step1 step={pipeline.step1} />
      <Step2 step={pipeline.step2} />
      <Step3 step={pipeline.step3} propertyId={propertyId} />
      <Step4 step={pipeline.step4} />
    </div>
  );
}
