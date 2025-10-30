# SmartDay Agent

FastAPI micro-agent that converts rough daily goals into a structured, time-blocked plan.

## Endpoints
- `POST /plan`
- `GET /health`

### Local run
```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
