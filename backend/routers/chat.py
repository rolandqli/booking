"""Chat endpoint using LangChain for AI-assisted booking."""
import os

from fastapi import APIRouter, HTTPException, status
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = """You are a helpful assistant for an AI-assisted booking system. 
You help users schedule appointments, find providers, and answer questions about the booking service. 
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


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Receive a chat message and return an AI response."""
    if not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request.message},
    ]

    try:
        response = llm.invoke(messages)
        return ChatResponse(response=response.content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM error: {str(e)}",
        )
