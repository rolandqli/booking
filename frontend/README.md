# Booking Calendar Frontend

Next.js frontend for the AI-assisted booking system. Displays a calendar with providers as columns and 30-minute time slots as rows.

## Tech Stack

- **Next.js** (App Router)
- **React**
- **TypeScript**
- **Tailwind CSS**

## Setup

1. Install dependencies:

   ```bash
   npm install
   ```

2. Create `.env.local` (optional; defaults to `http://localhost:8000`)

3. Ensure the backend is running.

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Build

```bash
npm run build
npm start
```

## Calendar UI

- **Columns:** Providers (from `/providers/`)
- **Rows:** 30-minute slots (8:00 AM–6:00 PM)
- **Appointments:** Filled cells spanning the correct number of slots
- **Colors:** Provider `color` or light blue (`#93c5fd`) if none
- **Navigation:** Prev / Today / Next to change the viewed date

## Integration tests (E2E)

Tests both frontend and backend using a **separate test database** (so it does not affect your dev data).

### Setup (one-time)

1. Create a second Supabase project at [supabase.com/dashboard](https://supabase.com/dashboard) for testing.
2. Run the migrations (001, 002, 003) in the test project's SQL editor.
3. Copy `backend/.env.test.example` to `backend/.env.test` and set your test project's URL and service role key.

### Run

```bash
npm run test:e2e
```

Playwright starts the backend with the test DB and the frontend, then runs the test.

To use your own running backend instead (e.g. already started with test DB):

```bash
USE_TEST_DB=0 npm run test:e2e
```

The test creates 2 providers, 1 client, 1 appointment (on the next day), then verifies:
- Initial page (today) shows no filled cells
- After clicking Next, one appointment block appears in the first provider’s column
