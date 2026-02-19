"""Integration tests for backend API. Require backend running and Supabase configured."""
import os
from datetime import datetime, timedelta

import pytest
import requests

API_URL = os.environ.get("API_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def api_available():
    """Skip tests if backend is not running."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=2)
        if not r.ok:
            pytest.skip("Backend not healthy")
    except requests.RequestException:
        pytest.skip("Backend not running - start with: uvicorn main:app --reload")


@pytest.fixture
def seed_data(api_available):
    """Create two providers, one client, one appointment (tomorrow)."""
    provider1 = requests.post(
        f"{API_URL}/providers/",
        json={"name": "Integration Provider A", "specialization": "Test", "color": "#34d399"},
        timeout=5,
    ).json()
    provider2 = requests.post(
        f"{API_URL}/providers/",
        json={"name": "Integration Provider B", "specialization": "Test", "color": "#f472b6"},
        timeout=5,
    ).json()
    client = requests.post(
        f"{API_URL}/clients/",
        json={"first_name": "Integration", "last_name": "Client", "email": "int@test.example"},
        timeout=5,
    ).json()

    tomorrow = datetime.utcnow() + timedelta(days=1)
    start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=30)

    appointment = requests.post(
        f"{API_URL}/appointments/",
        json={
            "client_id": client["id"],
            "provider_id": provider1["id"],
            "start_time": start.isoformat() + "Z",
            "end_time": end.isoformat() + "Z",
            "appointment_type": "Integration Test",
            "status": "scheduled",
        },
        timeout=5,
    ).json()

    return {
        "provider1": provider1,
        "provider2": provider2,
        "client": client,
        "appointment": appointment,
    }


def test_seeded_appointment_appears_in_provider_filter(seed_data):
    """Appointment is returned when filtering by its provider."""
    p1_id = seed_data["provider1"]["id"]
    apt_id = seed_data["appointment"]["id"]

    r = requests.get(f"{API_URL}/appointments/", params={"provider_id": p1_id}, timeout=5)
    assert r.status_code == 200
    appointments = r.json()
    ids = [a["id"] for a in appointments]
    assert apt_id in ids


def test_seeded_appointment_has_correct_provider_and_client(seed_data):
    """Appointment references the correct provider and client."""
    apt = seed_data["appointment"]
    p1 = seed_data["provider1"]
    client = seed_data["client"]

    assert apt["provider_id"] == p1["id"]
    assert apt["client_id"] == client["id"]
    assert apt["appointment_type"] == "Integration Test"
    assert apt["status"] == "scheduled"
