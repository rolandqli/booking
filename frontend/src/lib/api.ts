const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getProviders(): Promise<import("@/types").Provider[]> {
  return fetcher("/providers/");
}

export async function getAppointments(): Promise<import("@/types").Appointment[]> {
  return fetcher("/appointments/");
}

export async function getClients(): Promise<import("@/types").Client[]> {
  return fetcher("/clients/");
}
