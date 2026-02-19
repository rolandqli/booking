"""Provider CRUD operations for the AI-assisted booking system."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from database import get_supabase

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderCreate(BaseModel):
    """Schema for creating a provider."""

    name: str
    specialization: Optional[str] = None
    color: Optional[str] = None


class ProviderUpdate(BaseModel):
    """Schema for updating a provider."""

    name: Optional[str] = None
    specialization: Optional[str] = None
    color: Optional[str] = None


class ProviderResponse(BaseModel):
    """Schema for provider response."""

    id: UUID
    name: str
    specialization: Optional[str]
    color: Optional[str]
    created_at: datetime
    updated_at: datetime


@router.post("/", response_model=ProviderResponse)
def create_provider(provider: ProviderCreate):
    """Create a new provider."""
    supabase = get_supabase()
    data = provider.model_dump()
    data["updated_at"] = datetime.utcnow().isoformat()
    response = supabase.table("providers").insert(data).execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create provider",
        )
    return response.data[0]


@router.get("/", response_model=list[ProviderResponse])
def list_providers():
    """List all providers."""
    supabase = get_supabase()
    response = supabase.table("providers").select("*").order("name").execute()
    return response.data or []


@router.get("/{provider_id}", response_model=ProviderResponse)
def get_provider(provider_id: UUID):
    """Get a single provider by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("providers")
        .select("*")
        .eq("id", str(provider_id))
        .maybe_single()
        .execute()
    )
    if response.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )
    return response.data


@router.patch("/{provider_id}", response_model=ProviderResponse)
def update_provider(provider_id: UUID, provider: ProviderUpdate):
    """Update a provider."""
    supabase = get_supabase()
    data = provider.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    data["updated_at"] = datetime.utcnow().isoformat()
    response = (
        supabase.table("providers")
        .update(data)
        .eq("id", str(provider_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )
    return response.data[0]


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(provider_id: UUID):
    """Delete a provider."""
    supabase = get_supabase()
    response = (
        supabase.table("providers").delete().eq("id", str(provider_id)).execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )
    return None
