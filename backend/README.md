# Booking API

FastAPI backend for an AI-assisted booking system. Manages providers, rooms, clients, and appointments with Supabase as the database.

## Overview

- **Framework:** FastAPI
- **Database:** Supabase (PostgreSQL)
- **Auth:** Uses Supabase service role key (backend-only; extend for user auth as needed)

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment variables

Copy `.env.example` to `.env` and set:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (Project Settings → API) |

### 3. Database setup

Run migrations in the Supabase SQL Editor (in order):

1. `supabase/migrations/001_create_providers.sql`
2. `supabase/migrations/002_create_rooms_clients.sql`
3. `supabase/migrations/003_create_appointments.sql`

### 4. Run the server

```bash
uvicorn main:app --reload
```

API base URL: `http://localhost:8000`

- Swagger UI: `http://localhost:8000/docs`

---

## Project Structure

```
backend/
├── main.py              # FastAPI app, CORS, router registration
├── database.py          # Supabase client factory
├── requirements.txt
├── routers/
│   ├── providers.py     # Provider CRUD
│   ├── rooms.py         # Room CRUD
│   ├── clients.py       # Client CRUD
│   └── appointments.py  # Appointment CRUD (with reference validation)
└── tests/
    ├── conftest.py      # Pytest fixtures, in-memory Supabase mock
    └── test_crud.py     # CRUD and validation tests
```

---

## API Reference

### General

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API status |
| GET | `/health` | Health check |

### Providers

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/providers/` | Create provider |
| GET | `/providers/` | List all providers |
| GET | `/providers/{id}` | Get provider by ID |
| PATCH | `/providers/{id}` | Update provider |
| DELETE | `/providers/{id}` | Delete provider |

**Create body:** `{ "name": string, "specialization"?: string, "color"?: string }`

### Rooms

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rooms/` | Create room |
| GET | `/rooms/` | List all rooms |
| GET | `/rooms/{id}` | Get room by ID |
| PATCH | `/rooms/{id}` | Update room |
| DELETE | `/rooms/{id}` | Delete room |

**Create body:** `{ "name": string, "capacity"?: number }` (default capacity: 1)

### Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/clients/` | Create client |
| GET | `/clients/` | List all clients |
| GET | `/clients/{id}` | Get client by ID |
| PATCH | `/clients/{id}` | Update client |
| DELETE | `/clients/{id}` | Delete client |

**Create body:** `{ "first_name": string, "last_name": string, "email"?: string, "phone"?: string }`

### Appointments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/appointments/` | Create appointment |
| GET | `/appointments/` | List appointments (supports filters) |
| GET | `/appointments/{id}` | Get appointment by ID |
| PATCH | `/appointments/{id}` | Update appointment |
| DELETE | `/appointments/{id}` | Delete appointment |

**Create body:**

```json
{
  "client_id": "uuid",
  "provider_id": "uuid",
  "room_id": "uuid (optional)",
  "start_time": "ISO 8601 datetime",
  "end_time": "ISO 8601 datetime",
  "appointment_type": "string (optional)",
  "priority": 0 | 1 | 2,
  "status": "scheduled (default)"
}
```

**List query params:** `?client_id=uuid&provider_id=uuid&room_id=uuid&status=scheduled`

**Reference validation:** Creating an appointment requires that the `client_id` and `provider_id` exist. If `room_id` is provided, it must also exist. Otherwise the API returns `404` with `Client not found`, `Provider not found`, or `Room not found`.

---

## Database Schema

| Table | Key fields |
|-------|------------|
| `providers` | id, name, specialization, color |
| `rooms` | id, name, capacity |
| `clients` | id, first_name, last_name, email, phone |
| `appointments` | id, client_id, provider_id, room_id, start_time, end_time, appointment_type, priority, status |

- `appointments.client_id` → `clients(id)` ON DELETE CASCADE
- `appointments.provider_id` → `providers(id)` ON DELETE CASCADE
- `appointments.room_id` → `rooms(id)` (nullable)
- `priority`: 0 = normal, 1 = high, 2 = urgent
- `status`: e.g. `scheduled`, `completed`, `canceled`

---

## Testing

```bash
pytest tests/ -v
```

Tests use an in-memory mock of Supabase (no real DB). They cover CRUD for all resources and appointment validation when client, provider, or room references are missing.