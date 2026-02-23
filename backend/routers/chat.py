"""Chat endpoint using LangChain for AI-assisted booking."""
import os
import re
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from database import get_supabase

router = APIRouter(prefix="/chat", tags=["chat"])

_request_timezone: ContextVar[str] = ContextVar("request_timezone", default="UTC")


def _get_tz() -> str:
    return _request_timezone.get()


def _to_utc_str(dt: datetime) -> str:
    """Format timezone-aware datetime as ISO string for DB (UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_local_display(dt: datetime) -> tuple[str, str]:
    """(time_str, date_str) in user's timezone for display."""
    print(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    print(dt)
    local = dt.astimezone(ZoneInfo(_get_tz()))
    print(local)
    return local.strftime("%I:%M %p").lstrip("0"), local.strftime("%Y-%m-%d")


def _day_bounds_utc(dt_utc: datetime) -> tuple[str, str]:
    """Day boundaries (start, end) in UTC for the date of dt_utc in user's timezone."""
    tz = ZoneInfo(_get_tz())
    local = dt_utc.astimezone(tz)
    day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)
    return _to_utc_str(day_start.astimezone(timezone.utc)), _to_utc_str(
        day_end.astimezone(timezone.utc)
    )


SYSTEM_PROMPT = """You are a helpful assistant for an AI-assisted booking system. 
You help businesses schedule appointments with their clients, manage their providers, and reschedule appointments to avoid conflicts.
- get_affected_clients: sick days, who is affected, which clients have appointments with a provider
- check_availability: availability, fitting someone in, is a slot free
- create_appointment: book a new appointment (provider, client, time; room optional – will pick one if omitted)
- reschedule_appointment: move an existing appointment to a new time (identify by client, provider, old date/time)
For dates: YYYY-MM-DD, 'today', or 'tomorrow'. For time only, use 'today'.
Be concise and helpful. If you don't know something, say so."""


class ChatRequest(BaseModel):
    """Schema for chat request."""

    message: str
    timezone: Optional[str] = None  # IANA timezone e.g. America/New_York; uses UTC if omitted


class ChatResponse(BaseModel):
    """Schema for chat response."""

    response: str

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="OPENAI_API_KEY is not configured",
    )
llm = ChatOpenAI(
    model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-5-nano"),
    temperature=0.7,
    api_key=api_key,
)


def _parse_time(s: str) -> Optional[tuple[int, int]]:
    """Parse time string to (hour, minute). Supports 1, 1pm, 13:00, 1:30, etc."""
    s = s.strip().lower()
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) == "pm" and h < 12:
        h += 12
    elif m.group(3) == "am" and h == 12:
        h = 0
    elif not m.group(3) and h <= 12:
        if 1 <= h <= 7:
            h += 12  # "1" -> 1pm, "2" -> 2pm
    return (h, mi)


def _resolve_datetime(time_str: str, date_str: Optional[str] = None) -> Optional[datetime]:
    """Resolve time and optional date to timezone-aware UTC datetime. Uses user's timezone for 'today'/'tomorrow'."""
    parsed = _parse_time(time_str)
    if not parsed:
        return None
    hour, minute = parsed
    tz = ZoneInfo(_get_tz())
    now_local = datetime.now(tz)
    now_utc = now_local.astimezone(timezone.utc)

    if date_str and date_str.strip():
        s = date_str.strip().lower()
        if s == "today":
            dt_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        elif s == "tomorrow":
            dt_local = (now_local + timedelta(days=1)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        else:
            try:
                dt_local = datetime.strptime(s, "%Y-%m-%d").replace(
                    hour=hour, minute=minute, second=0, microsecond=0, tzinfo=tz
                )
            except ValueError:
                return None
        dt_utc = dt_local.astimezone(timezone.utc)
        return dt_utc if dt_utc >= now_utc else (dt_utc + timedelta(days=1))

    today_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    today_utc = today_local.astimezone(timezone.utc)
    return today_utc if today_utc >= now_utc else today_utc + timedelta(days=1)


def _resolve_date(date_str: str) -> Optional[tuple[datetime, datetime]]:
    """Resolve date string to (day_start_utc, day_end_utc) for DB queries."""
    s = date_str.strip().lower()
    tz = ZoneInfo(_get_tz())
    now_local = datetime.now(tz)
    if s == "today":
        day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    elif s == "tomorrow":
        day_start_local = (now_local + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        try:
            day_start_local = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=tz)
        except ValueError:
            return None
    day_end_local = day_start_local + timedelta(days=1) - timedelta(microseconds=1)
    return (
        day_start_local.astimezone(timezone.utc),
        day_end_local.astimezone(timezone.utc),
    )


@tool
def get_affected_clients(provider_name: str, date: str, time: Optional[str] = None) -> str:
    """Get the list of clients who have appointments with a given provider on a given date.
    Use when asked about sick days, affected patients/clients, or who has appointments with a provider.
    provider_name: name or partial name of the provider (e.g. 'Provider A', 'Dr. Smith').
    date: 'today', 'tomorrow', or YYYY-MM-DD. If only time context, use 'today' or omit and pass time.
    time: optional time (e.g. '13:00', '1pm'). If omitted, returns all appointments that day. If given, use closest upcoming datetime (today or tomorrow)."""
    supabase = get_supabase()

    providers_resp = (
        supabase.table("providers")
        .select("id, name")
        .ilike("name", f"%{provider_name}%")
        .execute()
    )
    providers = providers_resp.data or []
    if not providers:
        return f"No provider found matching '{provider_name}'."

    if time:
        resolved = _resolve_datetime(time, date or "today")
        if not resolved:
            return f"Could not parse time '{time}'. Use HH:MM or '1pm'."
        slot_start = _to_utc_str(resolved)
        slot_end = _to_utc_str(resolved + timedelta(minutes=30))
        day_start, day_end = _day_bounds_utc(resolved)
    else:
        bounds = _resolve_date(date)
        if not bounds:
            return f"Invalid date '{date}'. Use 'today', 'tomorrow', or YYYY-MM-DD."
        day_start_utc, day_end_utc = bounds
        day_start = _to_utc_str(day_start_utc)
        day_end = _to_utc_str(day_end_utc)

    results = []
    for p in providers:
        if time:
            pass  # day_start, day_end already set
            apts_resp = (
                supabase.table("appointments")
                .select("id, client_id, start_time, end_time, appointment_type, status")
                .eq("provider_id", p["id"])
                .gte("start_time", day_start)
                .lte("start_time", day_end)
                .neq("status", "canceled")
                .execute()
            )
            apts_raw = apts_resp.data or []
            apts = []
            for a in apts_raw:
                ast = datetime.fromisoformat(str(a["start_time"]).replace("Z", "+00:00"))
                aet = datetime.fromisoformat(str(a["end_time"]).replace("Z", "+00:00"))
                st = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
                se = datetime.fromisoformat(slot_end.replace("Z", "+00:00"))
                if st < aet and se > ast:
                    apts.append(a)
        else:
            apts_resp = (
                supabase.table("appointments")
                .select("id, client_id, start_time, end_time, appointment_type, status")
                .eq("provider_id", p["id"])
                .gte("start_time", day_start)
                .lte("start_time", day_end)
                .neq("status", "canceled")
                .execute()
            )
            apts = apts_resp.data or []
        if not apts:
            results.append(f"Provider '{p['name']}' has no appointments on {date}.")
            continue

        client_ids = list({a["client_id"] for a in apts})
        clients_resp = supabase.table("clients").select("id, first_name, last_name, email, phone").in_("id", client_ids).execute()
        clients = {c["id"]: c for c in (clients_resp.data or [])}

        date_display = _to_local_display(resolved)[1] if time else date
        lines = [f"Provider '{p['name']}' on {date_display} – {len(apts)} appointment(s), {len(client_ids)} affected client(s):"]
        for apt in apts:
            c = clients.get(apt["client_id"])
            name = f"{c['first_name']} {c['last_name']}" if c else "Unknown"
            apt_type = apt.get("appointment_type") or "—"
            lines.append(f"  • {name} ({apt_type})")
        results.append("\n".join(lines))

    return "\n\n".join(results)


@tool
def check_availability(time: str, date: Optional[str] = None) -> str:
    """Check which providers have availability at a given time (30-min slot).
    Use when asked about fitting someone in, urgency, availability, or if a slot is free (e.g. 'can we fit them in at 1?').
    time: time in HH:MM, H:MM, or 12h format (e.g. '13:00', '1', '1pm').
    date: optional. If omitted, assume today; if that time has passed, use tomorrow (closest upcoming). If given (YYYY-MM-DD), use that date."""
    resolved = _resolve_datetime(time, date or "today")
    if not resolved:
        return f"Could not parse time '{time}'. Use HH:MM or '1pm'."

    slot_start = _to_utc_str(resolved)
    slot_end = _to_utc_str(resolved + timedelta(minutes=30))
    day_start, day_end = _day_bounds_utc(resolved)

    supabase = get_supabase()
    providers_resp = supabase.table("providers").select("id, name").execute()
    providers = providers_resp.data or []
    if not providers:
        return "No providers in the system."

    booked_ids = set()
    apts_resp = (
        supabase.table("appointments")
        .select("provider_id, start_time, end_time")
        .gte("start_time", day_start)
        .lte("start_time", day_end)
        .neq("status", "canceled")
        .execute()
    )
    for apt in apts_resp.data or []:
        start_s = apt.get("start_time", "")
        end_s = apt.get("end_time", "")
        if start_s and end_s:
            apt_start = datetime.fromisoformat(start_s.replace("Z", "+00:00"))
            apt_end = datetime.fromisoformat(end_s.replace("Z", "+00:00"))
            res_start = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
            res_end = datetime.fromisoformat(slot_end.replace("Z", "+00:00"))
            if res_start < apt_end and res_end > apt_start:
                booked_ids.add(apt["provider_id"])

    available = [p for p in providers if p["id"] not in booked_ids]
    time_display, date_display = _to_local_display(resolved)

    if not available:
        return f"No providers available at {time_display} on {date_display}. All are booked."
    names = ", ".join(p["name"] for p in available)
    return f"At {time_display} on {date_display}: {len(available)} provider(s) available – {names}."


def _find_provider(supabase, name: str):
    r = supabase.table("providers").select("id, name").ilike("name", f"%{name}%").execute()
    rows = r.data or []
    return rows[0] if len(rows) == 1 else (rows[0] if rows else None)


def _find_client(supabase, name: str):
    parts = name.strip().split(maxsplit=1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    r = supabase.table("clients").select("id, first_name, last_name").execute()
    rows = r.data or []
    name_lower = name.lower()
    for c in rows:
        fn = (c.get("first_name") or "").lower()
        ln = (c.get("last_name") or "").lower()
        if name_lower in f"{fn} {ln}" or name_lower in f"{ln} {fn}":
            return c
    if first and last:
        for c in rows:
            if (c.get("first_name") or "").lower() == first.lower() and (c.get("last_name") or "").lower() == last.lower():
                return c
    if first:
        fl = first.lower()
        for c in rows:
            fn = (c.get("first_name") or "").lower()
            ln = (c.get("last_name") or "").lower()
            if fn == fl or ln == fl:
                return c
    return rows[0] if rows else None


def _get_rooms_booked_at(supabase, slot_start: str, slot_end: str) -> set:
    dt = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
    day_start, day_end = _day_bounds_utc(dt)
    r = (
        supabase.table("appointments")
        .select("room_id, start_time, end_time")
        .gte("start_time", day_start)
        .lte("start_time", day_end)
        .neq("status", "canceled")
        .execute()
    )
    booked = set()
    st = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
    se = datetime.fromisoformat(slot_end.replace("Z", "+00:00"))
    for a in r.data or []:
        if not a.get("room_id"):
            continue
        ast = datetime.fromisoformat(str(a["start_time"]).replace("Z", "+00:00"))
        aet = datetime.fromisoformat(str(a["end_time"]).replace("Z", "+00:00"))
        if st < aet and se > ast:
            booked.add(a["room_id"])
    return booked


def _get_providers_clients_booked_at(supabase, slot_start: str, slot_end: str) -> tuple[set, set]:
    dt = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
    day_start, day_end = _day_bounds_utc(dt)
    r = (
        supabase.table("appointments")
        .select("provider_id, client_id, start_time, end_time")
        .gte("start_time", day_start)
        .lt("start_time", day_end)
        .neq("status", "canceled")
        .execute()
    )
    providers_booked, clients_booked = set(), set()
    st = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
    se = datetime.fromisoformat(slot_end.replace("Z", "+00:00"))
    for a in r.data or []:
        ast = datetime.fromisoformat(str(a["start_time"]).replace("Z", "+00:00"))
        aet = datetime.fromisoformat(str(a["end_time"]).replace("Z", "+00:00"))
        if st < aet and se > ast:
            if a.get("provider_id"):
                providers_booked.add(a["provider_id"])
            if a.get("client_id"):
                clients_booked.add(a["client_id"])
    return providers_booked, clients_booked


@tool
def create_appointment(
    provider_name: str,
    client_name: str,
    time: str,
    date: Optional[str] = None,
    room_name: Optional[str] = None,
    appointment_type: Optional[str] = None,
) -> str:
    """Create a new appointment. Use when user wants to book or schedule an appointment.
    provider_name: name or partial name of the provider.
    client_name: client name (first, last, or both).
    time: e.g. '1pm', '13:00'.
    date: optional. Omit or 'today' for soonest. 'tomorrow' or YYYY-MM-DD for specific date.
    room_name: optional. If omitted, an available room is chosen automatically.
    appointment_type: optional (e.g. 'Consultation', 'Follow-up')."""
    supabase = get_supabase()
    provider = _find_provider(supabase, provider_name)
    if not provider:
        return f"No unique provider found matching '{provider_name}'."
    client = _find_client(supabase, client_name)
    if not client:
        return f"No client found matching '{client_name}'."

    resolved = _resolve_datetime(time, date or "today")
    if not resolved:
        return f"Could not parse time '{time}'."
    slot_start = _to_utc_str(resolved)
    slot_end = _to_utc_str(resolved + timedelta(minutes=30))

    providers_booked, clients_booked = _get_providers_clients_booked_at(
        supabase, slot_start, slot_end
    )
    if provider["id"] in providers_booked:
        return f"Provider {provider['name']} is already booked at that time."
    if client["id"] in clients_booked:
        return f"Client {client.get('first_name', '')} {client.get('last_name', '')} already has an appointment at that time."

    room_id = None
    if room_name:
        r = supabase.table("rooms").select("id, name").ilike("name", f"%{room_name}%").execute()
        rooms = r.data or []
        if not rooms:
            return f"No room found matching '{room_name}'."
        room_id = rooms[0]["id"]
        booked_rooms = _get_rooms_booked_at(supabase, slot_start, slot_end)
        if room_id in booked_rooms:
            return f"Room {rooms[0]['name']} is already booked at that time."
    else:
        rooms_resp = supabase.table("rooms").select("id, name").execute()
        all_rooms = rooms_resp.data or []
        booked_rooms = _get_rooms_booked_at(supabase, slot_start, slot_end)
        for rm in all_rooms:
            if rm["id"] not in booked_rooms:
                room_id = rm["id"]
                break

    data = {
        "client_id": client["id"],
        "provider_id": provider["id"],
        "start_time": slot_start,
        "end_time": slot_end,
        "status": "scheduled",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if room_id:
        data["room_id"] = room_id
    if appointment_type:
        data["appointment_type"] = appointment_type

    resp = supabase.table("appointments").insert(data).execute()
    if not resp.data:
        return "Failed to create appointment."
    apt = resp.data[0]
    room_str = f" in room {room_name or 'auto-assigned'}" if room_id else ""
    time_display, date_display = _to_local_display(resolved)
    return f"Appointment created: {client.get('first_name', '')} {client.get('last_name', '')} with {provider['name']} at {time_display} on {date_display}{room_str}."


@tool
def reschedule_appointment(
    client_name: str,
    provider_name: str,
    old_date: str,
    old_time: str,
    new_time: str,
    new_date: Optional[str] = None,
) -> str:
    """Reschedule an existing appointment to a new time. Use when user wants to move or change an appointment.
    client_name: client name.
    provider_name: provider name.
    old_date: current date ('today', 'tomorrow', or YYYY-MM-DD).
    old_time: current time (e.g. '1pm').
    new_time: new time (e.g. '2pm').
    new_date: optional new date. If omitted, same date as old_date."""
    supabase = get_supabase()
    provider = _find_provider(supabase, provider_name)
    if not provider:
        return f"No provider found matching '{provider_name}'."
    client = _find_client(supabase, client_name)
    if not client:
        return f"No client found matching '{client_name}'."

    old_dt = _resolve_datetime(old_time, old_date)
    if not old_dt:
        return f"Could not parse old time '{old_time}'."
    old_start = _to_utc_str(old_dt)
    old_end = _to_utc_str(old_dt + timedelta(minutes=30))

    new_dt = _resolve_datetime(
        new_time,
        new_date or (_to_local_display(old_dt)[1] if old_date else "today"),
    )
    if not new_dt:
        return f"Could not parse new time '{new_time}'."
    new_start = _to_utc_str(new_dt)
    new_end = _to_utc_str(new_dt + timedelta(minutes=30))

    day_s, day_e = _day_bounds_utc(old_dt)
    apts = (
        supabase.table("appointments")
        .select("id, start_time, end_time, room_id")
        .eq("client_id", client["id"])
        .eq("provider_id", provider["id"])
        .gte("start_time", day_s)
        .lt("start_time", day_e)
        .neq("status", "canceled")
        .execute()
    )
    rows = apts.data or []
    target = None
    os = datetime.fromisoformat(old_start.replace("Z", "+00:00"))
    oe = datetime.fromisoformat(old_end.replace("Z", "+00:00"))
    for a in rows:
        ast = datetime.fromisoformat(str(a["start_time"]).replace("Z", "+00:00"))
        aet = datetime.fromisoformat(str(a["end_time"]).replace("Z", "+00:00"))
        if os < aet and oe > ast:
            target = a
            break
    if not target:
        return f"No appointment found for {client.get('first_name', '')} {client.get('last_name', '')} with {provider['name']} at {old_time} on {old_date}."

    providers_booked, clients_booked = _get_providers_clients_booked_at(
        supabase, new_start, new_end
    )
    apt_id = target["id"]
    if provider["id"] in providers_booked:
        return f"Provider {provider['name']} is already booked at the new time."
    if client["id"] in clients_booked:
        return f"Client already has an appointment at the new time."

    room_id = target.get("room_id")
    if room_id:
        booked_rooms = _get_rooms_booked_at(supabase, new_start, new_end)
        new_day_start, new_day_end = _day_bounds_utc(new_dt)
        apts_in_slot = (
            supabase.table("appointments")
            .select("id, room_id, start_time, end_time")
            .gte("start_time", new_day_start)
            .lte("start_time", new_day_end)
            .neq("status", "canceled")
            .execute()
        )
        for a in apts_in_slot.data or []:
            if a.get("room_id") != room_id:
                continue
            ast = datetime.fromisoformat(str(a.get("start_time", "")).replace("Z", "+00:00"))
            aet = datetime.fromisoformat(str(a.get("end_time", "")).replace("Z", "+00:00"))
            ns = datetime.fromisoformat(new_start.replace("Z", "+00:00"))
            ne = datetime.fromisoformat(new_end.replace("Z", "+00:00"))
            if ns < aet and ne > ast and str(a.get("id")) != str(apt_id):
                return f"The room is already booked at the new time."

    supabase.table("appointments").update(
        {"start_time": new_start, "end_time": new_end, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", apt_id).execute()
    time_display, date_display = _to_local_display(new_dt)
    return f"Appointment rescheduled to {time_display} on {date_display}."



def _validate_timezone(tz: Optional[str]) -> str:
    """Return valid IANA timezone or 'UTC' if invalid/omitted."""
    if not tz or not tz.strip():
        return "UTC"
    tz = tz.strip()
    try:
        ZoneInfo(tz)
        return tz
    except Exception:
        return "UTC"


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Receive a chat message and return an AI response."""
    if not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )
    tz = _validate_timezone(request.timezone)
    token = _request_timezone.set(tz)
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=request.message),
        ]
        tools_by_name = {
            get_affected_clients.name: get_affected_clients,
            check_availability.name: check_availability,
            create_appointment.name: create_appointment,
            reschedule_appointment.name: reschedule_appointment,
        }
        llm_with_tools = llm.bind_tools(
            [get_affected_clients, check_availability, create_appointment, reschedule_appointment]
        )
        try:
            max_turns = 5
            for _ in range(max_turns):
                response = llm_with_tools.invoke(messages)
                if not getattr(response, "tool_calls", None):
                    return ChatResponse(response=response.content or "")
                messages.append(response)
                for tc in response.tool_calls:
                    name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                    args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                    tool = tools_by_name.get(name)
                    if not tool:
                        result = f"Unknown tool: {name}"
                    else:
                        result = tool.invoke(args)
                    messages.append(
                        ToolMessage(content=str(result), tool_call_id=tc_id)
                    )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM error: {str(e)}",
            )
        return ChatResponse(response="Sorry, I couldn't complete that request.")
    finally:
        _request_timezone.reset(token)
