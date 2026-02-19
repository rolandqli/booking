"use client";

import { useEffect, useState } from "react";
import Calendar from "@/components/Calendar";
import { getProviders, getAppointments, getClients } from "@/lib/api";
import type { Appointment, Provider, Client} from "@/types";

export default function Home() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewDate, setViewDate] = useState(new Date());

  useEffect(() => {
    Promise.all([getProviders(), getAppointments(), getClients()])
      .then(([p, a, c]) => {
        setProviders(p);
        setAppointments(a);
        setClients(c);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const prevDay = () =>
    setViewDate((d) => {
      const next = new Date(d);
      next.setDate(next.getDate() - 1);
      return next;
    });
  const nextDay = () =>
    setViewDate((d) => {
      const next = new Date(d);
      next.setDate(next.getDate() + 1);
      return next;
    });
  const today = () => setViewDate(new Date());

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-100">
        <p className="text-zinc-600">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-100">
        <p className="text-red-600">Error: {error}</p>
        <p className="text-sm text-zinc-600">Ensure the backend is running at http://localhost:8000</p>
      </div>
    );
  }

  const dateStr = viewDate.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="min-h-screen bg-zinc-100 p-4 md:p-6">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-2xl font-bold text-zinc-900">Booking Calendar</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={prevDay}
              className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
            >
              ← Prev
            </button>
            <button
              onClick={today}
              className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
            >
              Today
            </button>
            <button
              data-testid="nav-next"
              onClick={nextDay}
              className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
            >
              Next →
            </button>
            <span className="ml-2 text-sm font-medium text-zinc-600">{dateStr}</span>
          </div>
        </header>

        {providers.length === 0 ? (
          <div className="rounded-lg border border-zinc-200 bg-white p-8 text-center text-zinc-600">
            No providers yet. Add providers via the API to see the calendar.
          </div>
        ) : (
          <Calendar providers={providers} appointments={appointments} clients={clients} viewDate={viewDate} />
        )}
      </div>
    </div>
  );
}
