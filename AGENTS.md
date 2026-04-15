# Repository Guidelines

## Project Structure & Module Organization

This repository contains a React/Vite frontend, a Flask backend, and data exploration artifacts for the hotel review workflow.

- `frontend/`: main React app. Components live in `frontend/src/components/`, app-level styles in `frontend/src/App.css` and `frontend/src/index.css`, mock UI data in `frontend/src/data/`, and static public assets in `frontend/public/`.
- `backend/`: Flask API. `backend/main.py` creates the app, `backend/app/__init__.py` configures CORS and OpenAI setup, and route blueprints live under `backend/app/routes/`.
- `sources/`: source CSV data and `DICTIONARY.md`.
- `hybrid_test/`: notebook, pipeline scripts, and generated CSV outputs for amenity extraction experiments.
- `data-exploration-frontend/`: simple static HTML exploration UI.

## Product Context

This is a Wharton Hack-AI-thon prototype for "Ask What Matters: Adaptive AI for Smarter Travel Reviews." The goal is to ask travelers 1-2 low-friction follow-up questions that fill missing, stale, or disputed information about a hotel.

The intended data pipeline starts from the provided review and property datasets. A private preprocessing repo lives one directory above this project and currently produces JSON outputs that should be treated as the source-of-truth handoff into this public repo. Those outputs capture per-review, per-amenity signals such as sentiment, detail level, relative importance, reviewer knowledge, disagreement across reviews, and staleness. They are aggregated into per-hotel amenity priority scores that determine which follow-up questions matter most.

The collection flow should first offer an ElevenLabs voice interaction. If the user declines voice, fall back to a form. The question selector should intersect the highest-priority amenities for the hotel with amenities the reviewer says they actually used. Generated questions should be specific, easy to answer, and tied to the reason more information is needed.

The next implementation phase is to make the voice agent dynamic using those historical review outputs and to improve the end-to-end user flow. Keep that in mind when changing frontend state, backend endpoints, data schemas, or asset loading. Prefer integration points that can consume the JSON outputs directly, rather than re-deriving logic in the public repo unless it is necessary for UI behavior or validation.

## Build, Test, and Development Commands

Run frontend commands from `frontend/`:

- `npm install`: install Vite, React, and ESLint dependencies.
- `npm run dev`: start the local Vite server.
- `npm run build`: create a production build in `frontend/dist/`.
- `npm run lint`: run ESLint on JS/JSX files.
- `npm run preview`: preview the production build locally.

Run backend commands from `backend/`:

- `python -m venv venv`: create a local virtual environment.
- `pip install -r requirements.txt`: install Flask, OpenAI, pandas, and related dependencies.
- `python main.py`: start the Flask app in debug mode.
- `PORT=5001 python main.py`: start Flask on an alternate port if macOS or another local server is already using port 5000. When using a non-5000 backend port, start the frontend with `VITE_API_BASE_URL=http://localhost:5001 npm run dev`.

Local macOS quirk: port 5000 is often already occupied, commonly by AirPlay Receiver or a previously started Flask process. Do not assume port 5000 is available. If the backend reports `Address already in use`, use `PORT=5001 python main.py` and match the frontend API base URL.

For the static exploration page, run `python3 -m http.server 8000` from the repo root and open `/data-exploration-frontend/`.

## Coding Style & Naming Conventions

Use ES modules and JSX for frontend code. Follow the existing style: 2-space indentation, single quotes in JS config files, PascalCase React component files such as `PropertyCard.jsx`, and camelCase variables/functions. Keep reusable UI pieces in `frontend/src/components/`.

Use Python 3 for backend code with 4-space indentation. Keep API endpoints in route blueprints and shared API/client logic in `backend/app/`.

## Testing Guidelines

There is no formal automated test suite yet. Before opening a PR, run `npm run lint`, `npm run build`, and manually smoke test the Flask endpoint and frontend flow. If adding tests, place frontend tests near components with `*.test.jsx` naming and backend tests under `backend/tests/` with `test_*.py`.

## Agent-Specific Instructions

Preserve the MVP focus: adaptive review collection, not a general hotel review app. When adding preprocessing outputs, prefer explicit schemas for amenity-level scores and reasons so the frontend can explain why each question is being asked. Keep voice and form paths behaviorally aligned: they should collect the same amenity usage signals and answers, only through different input modes.

When merging work from the private preprocessing repo into this public repo, treat the JSON artifacts as external inputs and be deliberate about what gets copied into code versus what stays in generated data. Prefer small, auditable adapters for reading the private outputs, and avoid baking private-repo-only assumptions into reusable frontend or backend abstractions.

For dynamic question generation, optimize for amenity selection quality and traceability. The code should make it easy to answer: why was this amenity selected, what evidence supported it, and how does that map to the question the user sees.

For UX flow work, preserve the simple voice-first then form-fallback structure, but improve friction points around onboarding, amenity usage collection, and answer handoff. Make the flow feel cohesive across modes rather than building separate experiences.

## Commit & Pull Request Guidelines

Recent commits are short, imperative summaries such as `Polish UI details` and `Refine Expedia review UI`. Keep commits focused and describe the user-visible change.

Pull requests should include a brief summary, commands run, screenshots for UI changes, and notes about data or environment requirements. Do not commit secrets; use a local `.env` for `OPENAI_API_KEY`.
