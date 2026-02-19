import { test, expect } from "@playwright/test";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const E2E_CLIENT_FIRST = "E2ETestClient";
const E2E_CLIENT_LAST = "E2E";

async function clearTestDb(): Promise<void> {
  const [appointments, clients, providers, rooms] = await Promise.all([
    fetch(`${API_URL}/appointments/`).then((r) => r.json()),
    fetch(`${API_URL}/clients/`).then((r) => r.json()),
    fetch(`${API_URL}/providers/`).then((r) => r.json()),
    fetch(`${API_URL}/rooms/`).then((r) => r.json()),
  ]);

  for (const a of appointments) {
    await fetch(`${API_URL}/appointments/${a.id}`, { method: "DELETE" });
  }
  for (const c of clients) {
    await fetch(`${API_URL}/clients/${c.id}`, { method: "DELETE" });
  }
  for (const p of providers) {
    await fetch(`${API_URL}/providers/${p.id}`, { method: "DELETE" });
  }
  for (const r of rooms) {
    await fetch(`${API_URL}/rooms/${r.id}`, { method: "DELETE" });
  }
}

async function seedTestData(): Promise<{
  provider1Id: string;
  provider2Id: string;
  clientId: string;
  appointmentId: string;
}> {
  const provider1 = await fetch(`${API_URL}/providers/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: "E2E Provider A",
      specialization: "Test",
      color: "#34d399",
    }),
  }).then((r) => r.json());

  const provider2 = await fetch(`${API_URL}/providers/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: "E2E Provider B",
      specialization: "Test",
      color: "#f472b6",
    }),
  }).then((r) => r.json());

  const client = await fetch(`${API_URL}/clients/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      first_name: E2E_CLIENT_FIRST,
      last_name: E2E_CLIENT_LAST,
      email: "e2e@test.example",
    }),
  }).then((r) => r.json());

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const start = new Date(tomorrow.getFullYear(), tomorrow.getMonth(), tomorrow.getDate(), 10, 0);
  const end = new Date(tomorrow.getFullYear(), tomorrow.getMonth(), tomorrow.getDate(), 10, 30);

  const appointment = await fetch(`${API_URL}/appointments/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: client.id,
      provider_id: provider1.id,
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      appointment_type: "E2E Consultation",
      status: "scheduled",
    }),
  }).then((r) => r.json());

  return {
    provider1Id: provider1.id,
    provider2Id: provider2.id,
    clientId: client.id,
    appointmentId: appointment.id,
  };
}

test.describe("Calendar Integration", () => {
  test.beforeAll(async () => {
    const health = await fetch(`${API_URL}/health`);
    if (!health.ok) {
      throw new Error(
        `Backend not running at ${API_URL}. Start it with: cd backend && uvicorn main:app --reload`
      );
    }
    if (process.env.USE_TEST_DB !== "0") {
      await clearTestDb();
    }
  });

  test("shows no filled cells on initial page (today), shows appointment on next day in one provider column", async ({
    page,
  }) => {
    const { provider1Id } = await seedTestData();

    await page.goto("/");

    await expect(page.getByTestId("calendar")).toBeVisible({ timeout: 10000 });

    const initialBlocks = page.getByTestId("appointment-block");
    await expect(initialBlocks).toHaveCount(0);

    await page.getByTestId("nav-next").click();

    const blocksAfterNext = page.getByTestId("appointment-block");
    await expect(blocksAfterNext).toHaveCount(1);

    const block = blocksAfterNext.first();
    await expect(block).toHaveAttribute("data-provider-id", provider1Id);
    await expect(block).toContainText(E2E_CLIENT_FIRST);
    await expect(block).toContainText(E2E_CLIENT_LAST);
  });
});
