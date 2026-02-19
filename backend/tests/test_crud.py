"""CRUD tests for providers, rooms, clients, and appointments."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest


class TestProvidersCRUD:
    """Tests for provider CRUD operations."""

    def test_create_and_get_provider(self, client, mock_db):
        store, _ = mock_db
        response = client.post(
            "/providers/",
            json={"name": "Dr. Smith", "specialization": "General", "color": "#3498db"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Dr. Smith"
        assert data["specialization"] == "General"
        assert data["color"] == "#3498db"
        assert "id" in data
        assert "created_at" in data

        get_resp = client.get(f"/providers/{data['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Dr. Smith"

    def test_list_providers(self, client, mock_db):
        client.post("/providers/", json={"name": "Dr. A"})
        client.post("/providers/", json={"name": "Dr. B"})
        response = client.get("/providers/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_update_provider(self, client, mock_db):
        create = client.post("/providers/", json={"name": "Dr. X"})
        pid = create.json()["id"]
        response = client.patch(f"/providers/{pid}", json={"name": "Dr. X Updated"})
        assert response.status_code == 200
        assert response.json()["name"] == "Dr. X Updated"

    def test_delete_provider(self, client, mock_db):
        create = client.post("/providers/", json={"name": "Dr. Y"})
        pid = create.json()["id"]
        response = client.delete(f"/providers/{pid}")
        assert response.status_code == 204
        get_resp = client.get(f"/providers/{pid}")
        assert get_resp.status_code == 404


class TestRoomsCRUD:
    """Tests for room CRUD operations."""

    def test_create_and_list_rooms(self, client, mock_db):
        response = client.post("/rooms/", json={"name": "Room 101", "capacity": 4})
        assert response.status_code == 200
        assert response.json()["name"] == "Room 101"
        assert response.json()["capacity"] == 4

        list_resp = client.get("/rooms/")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1
        assert list_resp.json()[0]["name"] == "Room 101"


class TestClientsCRUD:
    """Tests for client CRUD operations."""

    def test_create_and_get_client(self, client, mock_db):
        response = client.post(
            "/clients/",
            json={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "phone": "(323) 555-1234",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Doe"
        assert data["email"] == "jane@example.com"
        assert data["phone"] == "(323) 555-1234"
        get_resp = client.get(f"/clients/{data['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["last_name"] == "Doe"


class TestAppointmentsCRUD:
    """Tests for appointment CRUD and reference validation."""

    def test_create_appointment_succeeds_when_refs_exist(self, client, mock_db):
        provider = client.post("/providers/", json={"name": "Dr. P"}).json()
        client_resp = client.post(
            "/clients/",
            json={"first_name": "John", "last_name": "Doe"},
        ).json()
        room = client.post("/rooms/", json={"name": "R1"}).json()

        start = datetime.utcnow() + timedelta(hours=1)
        end = start + timedelta(minutes=30)
        response = client.post(
            "/appointments/",
            json={
                "client_id": str(client_resp["id"]),
                "provider_id": str(provider["id"]),
                "room_id": str(room["id"]),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "appointment_type": "Consultation",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == client_resp["id"]
        assert data["provider_id"] == provider["id"]
        assert data["room_id"] == room["id"]
        assert data["status"] == "scheduled"

    def test_create_appointment_fails_when_client_not_found(self, client, mock_db):
        provider = client.post("/providers/", json={"name": "Dr. P"}).json()
        fake_client_id = str(uuid4())

        start = datetime.utcnow() + timedelta(hours=1)
        end = start + timedelta(minutes=30)
        response = client.post(
            "/appointments/",
            json={
                "client_id": fake_client_id,
                "provider_id": str(provider["id"]),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_create_appointment_fails_when_provider_not_found(self, client, mock_db):
        client_resp = client.post(
            "/clients/",
            json={"first_name": "John", "last_name": "Doe"},
        ).json()
        fake_provider_id = str(uuid4())

        start = datetime.utcnow() + timedelta(hours=1)
        end = start + timedelta(minutes=30)
        response = client.post(
            "/appointments/",
            json={
                "client_id": str(client_resp["id"]),
                "provider_id": fake_provider_id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 404
        assert "Provider not found" in response.json()["detail"]

    def test_create_appointment_fails_when_room_not_found(self, client, mock_db):
        provider = client.post("/providers/", json={"name": "Dr. P"}).json()
        client_resp = client.post(
            "/clients/",
            json={"first_name": "John", "last_name": "Doe"},
        ).json()
        fake_room_id = str(uuid4())

        start = datetime.utcnow() + timedelta(hours=1)
        end = start + timedelta(minutes=30)
        response = client.post(
            "/appointments/",
            json={
                "client_id": str(client_resp["id"]),
                "provider_id": str(provider["id"]),
                "room_id": fake_room_id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 404
        assert "Room not found" in response.json()["detail"]
