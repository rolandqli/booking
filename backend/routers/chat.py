"""Chat endpoint using LangChain for AI-assisted booking."""
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from database import get_supabase

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = """You are a helpful assistant for an AI-assisted booking system. 
You help businesses schedule appointments with their clients, manage their providers, and reschedule appointments to avoid conflicts.
When users ask about providers taking sick days, who is affected, or which clients have appointments with a provider on a given date, use the get_affected_clients tool.
For dates, use YYYY-MM-DD format (e.g. tomorrow = calculate the actual date).
Be concise and helpful. If you don't know something, say so."""


class ChatRequest(BaseModel):
    """Schema for chat request."""

    message: str


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


@tool
def get_affected_clients(provider_name: str, date: str) -> str:
    """Get the list of clients who have appointments with a given provider on a given date.
    Use when asked about sick days, affected patients/clients, or who has appointments with a provider.
    provider_name: name or partial name of the provider (e.g. 'Provider A', 'Dr. Smith').
    date: date in YYYY-MM-DD format (e.g. '2025-02-19')."""
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

    try:
        dt = datetime.strptime(date.strip(), "%Y-%m-%d")
    except ValueError:
        return f"Invalid date format '{date}'. Use YYYY-MM-DD."

    day_start = dt.strftime("%Y-%m-%dT00:00:00")
    day_end = dt.strftime("%Y-%m-%dT23:59:59")

    results = []
    for p in providers:
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

        lines = [f"Provider '{p['name']}' on {date} – {len(apts)} appointment(s), {len(client_ids)} affected client(s):"]
        for apt in apts:
            c = clients.get(apt["client_id"])
            name = f"{c['first_name']} {c['last_name']}" if c else "Unknown"
            apt_type = apt.get("appointment_type") or "—"
            lines.append(f"  • {name} ({apt_type})")
        results.append("\n".join(lines))

    return "\n\n".join(results)




@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Receive a chat message and return an AI response."""
    if not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=request.message),
    ]

    tools_by_name = {get_affected_clients.name: get_affected_clients}

    try:
        max_turns = 5
        for _ in range(max_turns):
            response = llm.invoke(messages)
            if not getattr(response, "tool_calls", None):
                return ChatResponse(response=response.content or "")

            messages.append(response)
            for tc in response.tool_calls:
                name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                tool = tools_by_name.get(name, get_affected_clients)
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
