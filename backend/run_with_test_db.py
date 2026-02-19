"""Run the backend server using the test database. Loads .env.test before starting."""
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load test env before any app imports (so database.py gets test credentials)
env_path = Path(__file__).parent / ".env.test"
if not env_path.exists():
    print("Error: .env.test not found. Copy backend/.env.test.example to backend/.env.test", file=sys.stderr)
    print("and configure your test Supabase project.", file=sys.stderr)
    sys.exit(1)
load_dotenv(env_path)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
