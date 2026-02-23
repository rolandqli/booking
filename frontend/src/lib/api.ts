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

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function sendChatMessage(
  message: string,
  options?: { timezone?: string; history?: ChatMessage[] }
): Promise<{ response: string }> {
  const tz = options?.timezone ?? (typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : undefined);
  const res = await fetch(`${API_BASE}/chat/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, timezone: tz, history: options?.history ?? [] }),
  });
  if (!res.ok) throw new Error(`Chat error: ${res.status}`);
  return res.json();
}
