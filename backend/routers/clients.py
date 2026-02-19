"""Client CRUD operations for the AI-assisted booking system."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from database import get_supabase

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientCreate(BaseModel):
    """Schema for creating a client."""

    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class ClientUpdate(BaseModel):
    """Schema for updating a client."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ClientResponse(BaseModel):
    """Schema for client response."""

    id: UUID
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    created_at: datetime
    updated_at: datetime


@router.post("/", response_model=ClientResponse)
def create_client(client: ClientCreate):
    """Create a new client."""
    supabase = get_supabase()
    data = client.model_dump()
    data["updated_at"] = datetime.utcnow().isoformat()
    response = supabase.table("clients").insert(data).execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create client",
        )
    return response.data[0]


@router.get("/", response_model=list[ClientResponse])
def list_clients():
    """List all clients."""
    supabase = get_supabase()
    response = (
        supabase.table("clients")
        .select("*")
        .order("last_name")
        .order("first_name")
        .execute()
    )
    return response.data or []


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: UUID):
    """Get a single client by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("clients")
        .select("*")
        .eq("id", str(client_id))
        .maybe_single()
        .execute()
    )
    if response.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )
    return response.data


@router.patch("/{client_id}", response_model=ClientResponse)
def update_client(client_id: UUID, client: ClientUpdate):
    """Update a client."""
    supabase = get_supabase()
    data = client.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    data["updated_at"] = datetime.utcnow().isoformat()
    response = (
        supabase.table("clients")
        .update(data)
        .eq("id", str(client_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )
    return response.data[0]


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: UUID):
    """Delete a client."""
    supabase = get_supabase()
    response = (
        supabase.table("clients").delete().eq("id", str(client_id)).execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )
    return None
