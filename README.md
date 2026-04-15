Data Exploration Frontend (vibecoded lol):
Run with "python3 -m http.server 8000" from root then go to "http://localhost:8000/data-exploration-frontend/"

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
