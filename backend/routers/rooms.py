"""Room CRUD operations for the AI-assisted booking system."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from database import get_supabase

router = APIRouter(prefix="/rooms", tags=["rooms"])


class RoomCreate(BaseModel):
    """Schema for creating a room."""

    name: str
    capacity: Optional[int] = 1


class RoomUpdate(BaseModel):
    """Schema for updating a room."""

    name: Optional[str] = None
    capacity: Optional[int] = None


class RoomResponse(BaseModel):
    """Schema for room response."""

    id: UUID
    name: str
    capacity: int
    created_at: datetime
    updated_at: datetime


@router.post("/", response_model=RoomResponse)
def create_room(room: RoomCreate):
    """Create a new room."""
    supabase = get_supabase()
    data = room.model_dump()
    data["updated_at"] = datetime.utcnow().isoformat()
    response = supabase.table("rooms").insert(data).execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create room",
        )
    return response.data[0]


@router.get("/", response_model=list[RoomResponse])
def list_rooms():
    """List all rooms."""
    supabase = get_supabase()
    response = supabase.table("rooms").select("*").order("name").execute()
    return response.data or []


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(room_id: UUID):
    """Get a single room by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("rooms")
        .select("*")
        .eq("id", str(room_id))
        .maybe_single()
        .execute()
    )
    if response.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    return response.data


@router.patch("/{room_id}", response_model=RoomResponse)
def update_room(room_id: UUID, room: RoomUpdate):
    """Update a room."""
    supabase = get_supabase()
    data = room.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    data["updated_at"] = datetime.utcnow().isoformat()
    response = (
        supabase.table("rooms")
        .update(data)
        .eq("id", str(room_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    return response.data[0]


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: UUID):
    """Delete a room."""
    supabase = get_supabase()
    response = supabase.table("rooms").delete().eq("id", str(room_id)).execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    return None
