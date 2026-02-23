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


def _times_overlap(
    start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime
) -> bool:
    """Return True if the two time ranges overlap."""
    return start_a < end_b and end_a > start_b

def _check_all_appointments_for_overlap(
    supabase,
    person_id: UUID,
    person_type: str,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: Optional[UUID] = None,
) -> None:
    """Raise HTTPException if any appointment overlaps with the given time range."""
    id_type = f"{person_type.lower()}_id"
    appointments = (
        supabase.table("appointments")
        .select("id, start_time, end_time, status")
        .eq(id_type, str(person_id))
        .neq("status", "canceled")
        .execute()
    )
    for apt in appointments.data or []:
        if exclude_appointment_id and str(apt["id"]) == str(exclude_appointment_id):
            continue
        existing_start = datetime.fromisoformat(apt["start_time"].replace("Z", "+00:00"))
        existing_end = datetime.fromisoformat(apt["end_time"].replace("Z", "+00:00"))
        if _times_overlap(start_time, end_time, existing_start, existing_end):
            detail = f"{person_type} already has an appointment at this time"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )


def _check_no_room_overlap(
    supabase,
    room_id: UUID,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: Optional[UUID] = None,
) -> None:
    """Raise HTTPException if room is already booked at this time."""
    _check_all_appointments_for_overlap(
        supabase,
        room_id,
        "room",
        start_time,
        end_time,
        exclude_appointment_id=exclude_appointment_id,
    )

def _check_no_client_provider_overlap(
    supabase,
    client_id: UUID,
    provider_id: UUID,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: Optional[UUID] = None,
) -> None:
    """Raise HTTPException if client or provider already has an appointment at the same time."""
    for person_id, person_type in [(client_id, "Client"), (provider_id, "Provider")]:
        _check_all_appointments_for_overlap(
            supabase,
            person_id=person_id,
            person_type=person_type,
            start_time=start_time,
            end_time=end_time,
            exclude_appointment_id=exclude_appointment_id,
        )


def _validate_appointment_references(supabase, client_id: UUID, provider_id: UUID, room_id: Optional[UUID]) -> None:
    """Raise HTTPException if client, provider, or room (if provided) do not exist."""
    client_resp = (
        supabase.table("clients")
        .select("id")
        .eq("id", str(client_id))
        .maybe_single()
        .execute()
    )
    if client_resp.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    provider_resp = (
        supabase.table("providers")
        .select("id")
        .eq("id", str(provider_id))
        .maybe_single()
        .execute()
    )
    if provider_resp.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        )
    if room_id is not None:
        room_resp = (
            supabase.table("rooms")
            .select("id")
            .eq("id", str(room_id))
            .maybe_single()
            .execute()
        )
        if room_resp.data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found",
            )


@router.post("/", response_model=AppointmentResponse)
def create_appointment(appointment: AppointmentCreate):
    """Create a new appointment."""
    supabase = get_supabase()
    _validate_appointment_references(
        supabase,
        appointment.client_id,
        appointment.provider_id,
        appointment.room_id,
    )
    _check_no_client_provider_overlap(
        supabase,
        appointment.client_id,
        appointment.provider_id,
        appointment.start_time,
        appointment.end_time,
    )
    if appointment.room_id is not None:
        _check_no_room_overlap(
            supabase,
            appointment.room_id,
            appointment.start_time,
            appointment.end_time,
        )
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
    existing = (
        supabase.table("appointments")
        .select("*")
        .eq("id", str(appointment_id))
        .maybe_single()
        .execute()
    )
    if existing.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    data = appointment.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    effective = {**existing.data, **data}
    client_id = effective.get("client_id")
    provider_id = effective.get("provider_id")
    start_time = effective.get("start_time")
    end_time = effective.get("end_time")
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    _validate_appointment_references(
        supabase,
        client_id,
        provider_id,
        effective.get("room_id"),
    )
    _check_no_client_provider_overlap(
        supabase,
        client_id,
        provider_id,
        start_time,
        end_time,
        exclude_appointment_id=appointment_id,
    )
    room_id = effective.get("room_id")
    if room_id is not None:
        _check_no_room_overlap(
            supabase,
            room_id,
            start_time,
            end_time,
            exclude_appointment_id=appointment_id,
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
