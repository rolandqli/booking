"""Appointment CRUD operations for the AI-assisted booking system."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from database import get_supabase

router = APIRouter(prefix="/appointments", tags=["appointments"])


class AppointmentCreate(BaseModel):
    """Schema for creating an appointment."""

    client_id: UUID
    provider_id: UUID
    room_id: Optional[UUID] = None
    start_time: datetime
    end_time: datetime
    appointment_type: Optional[str] = None
    priority: Optional[int] = Field(default=0, ge=0, le=2)
    status: Optional[str] = "scheduled"


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""

    client_id: Optional[UUID] = None
    provider_id: Optional[UUID] = None
    room_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    appointment_type: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0, le=2)
    status: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Schema for appointment response."""

    id: UUID
    client_id: UUID
    provider_id: UUID
    room_id: Optional[UUID]
    start_time: datetime
    end_time: datetime
    appointment_type: Optional[str]
    priority: int
    status: str
    created_at: datetime
    updated_at: datetime


def _serialize_uuid(v):
    """Convert UUID to string for Supabase."""
    return str(v) if v is not None else None


@router.post("/", response_model=AppointmentResponse)
def create_appointment(appointment: AppointmentCreate):
    """Create a new appointment."""
    supabase = get_supabase()
    data = appointment.model_dump()
    data = {k: _serialize_uuid(v) for k, v in data.items()}
    data["updated_at"] = datetime.utcnow().isoformat()
    response = supabase.table("appointments").insert(data).execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create appointment",
        )
    return response.data[0]


@router.get("/", response_model=list[AppointmentResponse])
def list_appointments(
    client_id: Optional[UUID] = Query(None, description="Filter by client"),
    provider_id: Optional[UUID] = Query(None, description="Filter by provider"),
    room_id: Optional[UUID] = Query(None, description="Filter by room"),
    appointment_status: Optional[str] = Query(
        None, alias="status", description="Filter by status"
    ),
):
    """List appointments, optionally filtered."""
    supabase = get_supabase()
    query = supabase.table("appointments").select("*").order("start_time")
    if client_id:
        query = query.eq("client_id", str(client_id))
    if provider_id:
        query = query.eq("provider_id", str(provider_id))
    if room_id:
        query = query.eq("room_id", str(room_id))
    if appointment_status:
        query = query.eq("status", appointment_status)
    response = query.execute()
    return response.data or []


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(appointment_id: UUID):
    """Get a single appointment by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("appointments")
        .select("*")
        .eq("id", str(appointment_id))
        .maybe_single()
        .execute()
    )
    if response.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return response.data


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(appointment_id: UUID, appointment: AppointmentUpdate):
    """Update an appointment."""
    supabase = get_supabase()
    data = appointment.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    data = {k: _serialize_uuid(v) for k, v in data.items()}
    data["updated_at"] = datetime.utcnow().isoformat()
    response = (
        supabase.table("appointments")
        .update(data)
        .eq("id", str(appointment_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return response.data[0]


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(appointment_id: UUID):
    """Delete an appointment."""
    supabase = get_supabase()
    response = (
        supabase.table("appointments")
        .delete()
        .eq("id", str(appointment_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return None
