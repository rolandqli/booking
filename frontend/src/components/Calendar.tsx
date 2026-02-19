"use client";

import React, { useMemo } from "react";
import type { Appointment, Provider, Client } from "@/types";

const SLOT_MINUTES = 30;
const DEFAULT_COLOR = "#93c5fd"; // light blue
const SLOT_HEIGHT = 48;
const START_HOUR = 9;
const END_HOUR = 17;

function getSlotIndex(date: Date): number {
  const hours = date.getHours();
  const minutes = date.getMinutes();
  const totalMinutes = (hours - START_HOUR) * 60 + minutes;
  return Math.floor(totalMinutes / SLOT_MINUTES);
}

function getSlotSpan(startDate: Date, endDate: Date): number {
  const ms = endDate.getTime() - startDate.getTime();
  return Math.ceil(ms / (SLOT_MINUTES * 60 * 1000));
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

interface CalendarProps {
  providers: Provider[];
  appointments: Appointment[];
  clients: Client[];
  viewDate: Date;
}

export default function Calendar({
  providers,
  appointments,
  clients,
  viewDate,
}: CalendarProps) {
  const slots = useMemo(() => {
    const list: Date[] = [];
    for (let h = START_HOUR; h < END_HOUR; h++) {
      list.push(new Date(viewDate.getFullYear(), viewDate.getMonth(), viewDate.getDate(), h, 0));
      list.push(new Date(viewDate.getFullYear(), viewDate.getMonth(), viewDate.getDate(), h, 30));
    }
    return list;
  }, [viewDate]);

  const providerMap = useMemo(() => {
    const m = new Map<string, Provider>();
    providers.forEach((p) => m.set(p.id, p));
    return m;
  }, [providers]);

  const clientMap = useMemo(() => {
    const m = new Map<string, Client>();
    clients.forEach((c) => m.set(c.id, c));
    return m;
  }, [clients]);

  const appointmentsByProvider = useMemo(() => {
    const byProvider = new Map<string, Array<Appointment & { slotStart: number; span: number }>>();
    appointments.forEach((apt) => {
      const start = new Date(apt.start_time);
      const end = new Date(apt.end_time);
      if (!isSameDay(start, viewDate)) return;
      const slotStart = getSlotIndex(start);
      const span = getSlotSpan(start, end);
      if (slotStart < 0 || slotStart + span > slots.length) return;
      const list = byProvider.get(apt.provider_id) ?? [];
      list.push({ ...apt, slotStart, span });
      byProvider.set(apt.provider_id, list);
    });
    return byProvider;
  }, [appointments, viewDate, slots.length]);

  const formatTime = (d: Date) =>
    d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });

  return (
    <div data-testid="calendar" className="overflow-auto rounded-lg border border-zinc-200 bg-white">
      <div
        className="grid min-w-[600px]"
        style={{
          gridTemplateColumns: `80px repeat(${providers.length}, minmax(120px, 1fr))`,
          gridTemplateRows: `auto repeat(${slots.length}, ${SLOT_HEIGHT}px)`,
        }}
      >
        {/* Corner */}
        <div className="sticky left-0 top-0 z-10 border-b border-r border-zinc-200 bg-zinc-50 p-2 font-medium text-zinc-600">
          Time
        </div>

        {/* Provider headers */}
        {providers.map((p) => (
          <div
            key={p.id}
            className="border-b border-zinc-200 bg-zinc-50 p-2 text-center font-medium text-zinc-700"
          >
            {p.name}
            {p.specialization && (
              <span className="block text-xs font-normal text-zinc-500">{p.specialization}</span>
            )}
          </div>
        ))}

        {/* Time labels + grid cells */}
        {slots.map((slot, i) => (
          <React.Fragment key={`row-${i}`}>
            <div
              className="sticky left-0 z-10 border-b border-r border-zinc-200 bg-white py-1 pr-2 text-right text-sm text-zinc-500"
              style={{ height: SLOT_HEIGHT }}
            >
              {formatTime(slot)}
            </div>
            {providers.map((provider) => {
              const apts = appointmentsByProvider.get(provider.id) ?? [];
              const aptInThisSlot = apts.find(
                (a) => a.slotStart === i || (i > a.slotStart && i < a.slotStart + a.span)
              );
              const isFirstSlotOfApt = aptInThisSlot?.slotStart === i;

              return (
                <div
                  key={`${provider.id}-${i}`}
                  className="relative border-b border-r border-zinc-100"
                  style={{ height: SLOT_HEIGHT }}
                >
                  {isFirstSlotOfApt && aptInThisSlot && (
                    <div
                      data-testid="appointment-block"
                      data-provider-id={aptInThisSlot.provider_id}
                      className="absolute inset-x-1 overflow-hidden rounded px-2 py-1 text-xs font-medium text-zinc-800 shadow-sm"
                      style={{
                        top: 2,
                        bottom: 2,
                        height: aptInThisSlot.span * SLOT_HEIGHT - 4,
                        backgroundColor:
                          providerMap.get(aptInThisSlot.provider_id)?.color ?? DEFAULT_COLOR,
                      }}
                    >
                      {clientMap.get(aptInThisSlot.client_id)?.first_name ?? "Appointment"} { " "}
                      {clientMap.get(aptInThisSlot.client_id)?.last_name ?? "Appointment"}
                    </div>
                  )}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
