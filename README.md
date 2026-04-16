Data Exploration Frontend:
Run with "python3 -m http.server 8000" from root then go to "http://localhost:8000/data-exploration-frontend/"

URL: https://wharton-hackathon-2026.vercel.app/

frontend
- run with `npm run dev` in the frontend directory
- may need to `npm install` inside frontend directory as well

backend
- run with python main.py in the backend directory
- would recommend making venv `python -m venv venv` and `pip install -r requirements.txt`
- if port 5000 is already in use on macOS, run `PORT=5001 python main.py`
- when using port 5001, start the frontend with `VITE_API_BASE_URL=http://localhost:5001 npm run dev`

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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

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