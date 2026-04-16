# Holiway — Wharton Hack-AI-thon 2026

Currently hosted at https://wharton-hackathon-2026.vercel.app/

AI-powered hotel review collection platform built on the Expedia Group dataset. Holiway identifies which amenities are under-reviewed for a given property, generates targeted questions for arriving guests, and collects feedback via voice (ElevenLabs) or a structured text form.

---

<<<<<<< HEAD
dynamic review flow
- preprocessing artifacts from the private pipeline now live in `final-preprocessing/`, `preprocessing/`, and `scoring/`
- `scoring/ask_scores.json` drives the dynamic amenity targets for each property
- run the backend and open `http://localhost:5000/pipeline-demo` or `http://localhost:5000/property` to show the judge-facing pipeline visualizations
- if you started the backend with `PORT=5001`, use `http://localhost:5001/pipeline-demo` and `http://localhost:5001/property`
- the React app fetches `GET /api/review-session` and passes a compact target-amenity context into the ElevenLabs voice flow
- voice transcript extraction uses `POST /api/reviews/voice/extract` and requires `OPENAI_API_KEY`; the rest of the demo works from the checked-in JSON


# Expedia Review Intelligence — Wharton Hackathon 2026

A full-stack AI-powered hotel review platform that transforms the guest feedback experience using voice AI and dynamic amenity targeting. Guests leave reviews by talking naturally for 30 seconds; property managers get a real-time dashboard showing exactly which amenities need more guest input and why.

**Live demo:** https://wharton-hackathon-2026.vercel.app/

---

## What we built

Most hotel reviews are either too generic to be useful or never written at all. We built a system that:

- **Dynamically targets** the amenity gaps that matter most for each property, based on existing review analysis
- **Lets guests review by voice** — a 30-second conversation with an AI agent that asks the right follow-up questions
- **Extracts structured insights** from voice transcripts using GPT, feeding them back into the manager dashboard
- **Shows property managers** exactly what future travelers are still wondering about, not just aggregate star ratings

---

## Running locally
=======
## How it works

1. **Amenity scoring** — A preprocessing pipeline scores every amenity at every property across four dimensions: knowledge gaps, review controversy, sentiment decline, and staleness. The combined "ask score" determines which amenities are most worth asking about.
2. **Review sessions** — When a guest checks in, the app presents the top-scoring amenities for that property and generates plain-language questions to ask.
3. **Voice or text collection** — Guests can answer via a live AI voice agent (ElevenLabs Conversational AI) or a step-by-step text form. Voice transcripts are parsed to extract per-amenity answers.
4. **Manager dashboard** — Property managers see an overview of their review coverage and gaps.

---

## Data files

The raw CSVs are **not committed**. Place them at:

```
backend/sources/
├── Description_PROC.csv
└── Reviews_PROC.csv
```

---

## Setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `backend/.env` file:

```
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=...
```

Start the server (runs on port 5000):

```bash
python main.py
```
>>>>>>> 5b1cabb (readme updates)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

<<<<<<< HEAD
Runs at `http://localhost:5173` by default.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Runs at `http://localhost:5000` by default.

> **macOS port conflict:** If port 5000 is in use, run with:
> ```bash
> PORT=5001 python main.py
> ```
> Then start the frontend with:
> ```bash
> VITE_API_BASE_URL=http://localhost:5001 npm run dev
> ```

### Data exploration frontend

```bash
# From the project root
python3 -m http.server 8000
```

Then open `http://localhost:8000/data-exploration-frontend/`

---

## Judge-facing pipeline visualizations

With the backend running, open either of these in your browser:
http://localhost:5000/pipeline-demo
http://localhost:5000/property

---

## Key API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/properties` | List all demo properties |
| `GET` | `/api/review-session/:id` | Load dynamic review session with amenity targets |
| `GET` | `/api/manager/overview/:id` | Property manager dashboard data |
| `GET` | `/api/elevenlabs/signed-url` | Signed URL for voice session |
| `POST` | `/api/reviews/voice/extract` | Extract structured data from voice transcript |

---

## Environment variables

### Frontend (`frontend/.env`)
VITE_API_BASE_URL=http://localhost:5000
### Backend
OPENAI_API_KEY=your_key_here
ELEVENLABS_API_KEY=your_key_here

> **Note:** Voice transcript extraction via `POST /api/reviews/voice/extract` requires `OPENAI_API_KEY`. All other demo functionality works from the checked-in JSON artifacts without any API keys.

---

## How the dynamic review flow works

1. `scoring/ask_scores.json` ranks amenities per property by how much useful review coverage is missing
2. `GET /api/review-session` returns the top amenity targets for that property
3. The React app passes a compact amenity context into the ElevenLabs voice agent
4. The agent conducts a natural 30-second conversation, asking about the specific amenities that need coverage
5. On completion, `POST /api/reviews/voice/extract` uses GPT to extract structured answers from the transcript
6. The manager dashboard reflects updated sentiment and coverage data

---

## How the scoring pipeline works

1. Raw hotel reviews are processed through `final-preprocessing/` to build amenity and review profiles
2. `build_amenity_profiles.py` clusters mentions by amenity across all reviews
3. `gap_score_components.py` identifies which amenities lack recent, specific, or positive coverage
4. `scoring/calculate_score.py` combines gap signals into a single `ask_score` per amenity per property
5. Results are written to `scoring/ask_scores.json` and consumed by the backend at runtime

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React, Vite |
| Voice AI | ElevenLabs Conversational AI |
| Transcript extraction | OpenAI GPT |
| Backend | Python, Flask |
| Hosting | Vercel (frontend) |

---

## Team

Built at the Wharton Hackathon 2026.
=======
Then open `http://localhost:5173`.

---

## Preprocessing (one-time)

These scripts are already done and their outputs are committed. Re-run only if the source data changes.

### Build amenity taxonomy (~30 s)

Calls GPT-4o once to map all raw amenity strings to short canonical names, pruning non-guest-facing entries (measurements, eco-labels, policy text).

```bash
cd backend/final-preprocessing
python build_amenity_taxonomy.py
```

Output: `backend/sources/amenity_taxonomy.json`

| Raw string | Canonical name |
|---|---|
| `"full breakfast available for a fee 6:30 am–11:00 am"` | `"breakfast"` |
| `"available in all rooms: free wifi"` | `"wifi"` |
| `"at least 80% lighting from leds"` | *(pruned)* |

### Build review profiles and ask scores

```bash
python build_review_profiles.py
python build_amenity_profiles.py
python gap_score_components.py
python aggregate_reasons.py
```

### Precompute frontend review sessions

```bash
cd backend
python precompute_review_sessions.py
```

Output: `frontend/public/data/review-sessions.json`

---

## API reference

### Review sessions

| Method | Path | Description |
|---|---|---|
| GET | `/api/properties` | All scored properties (id, name, city, country) |
| GET | `/api/review-sessions` | All precomputed review sessions |
| GET | `/api/review-session/<property_id>` | Review session for a specific property |

### Voice

| Method | Path | Description |
|---|---|---|
| GET | `/api/elevenlabs/conversation-token` | Short-lived token for ElevenLabs conversation |
| GET | `/api/elevenlabs/signed-url` | Signed WebSocket URL for ElevenLabs agent |
| POST | `/api/reviews/voice/extract` | Extract per-amenity answers from a voice transcript |

### Manager

| Method | Path | Description |
|---|---|---|
| GET | `/api/manager/overview/<property_id>` | Review coverage overview for managers |
| GET | `/api/manager/review-sample/<property_id>` | Sample reviews for a property |

### AI

| Method | Path | Description |
|---|---|---|
| POST | `/api/ask` | Ask a free-form question about a property |

### Demo / walkthrough

| Method | Path | Description |
|---|---|---|
| GET | `/api/demo/properties` | Properties available in the pipeline demo |
| GET | `/api/demo/gap-data/<property_id>` | Raw gap-score breakdown for demo |
| GET | `/api/demo/property-detail/<property_id>` | Full property detail for demo |
| GET | `/api/demo/review-sample/<property_id>` | Sample reviews for demo |

---

## Data exploration frontend

A standalone static site for browsing the raw dataset — no server or build step needed.

1. Open `data-exploration-frontend/index.html` in a browser.
2. Use **Load CSVs** to load `Description_PROC.csv` and `Reviews_PROC.csv` from your local machine.
3. Click any property to see rating distribution, review timeline, and amenity breakdown.
>>>>>>> 5b1cabb (readme updates)
