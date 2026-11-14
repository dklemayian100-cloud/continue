from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field


# ---- Users ----
class UserCreate(BaseModel):
    phone_number: str
    full_name: str
    email: Optional[EmailStr] = None
    password: str
    role: str = "customer"
    county: Optional[str] = None
    town: Optional[str] = None


class UserOut(BaseModel):
    user_id: str
    phone_number: str
    full_name: str
    role: str
    wallet_balance: Decimal

    class Config:
        from_attributes = True


# ---- Venues ----
class VenueCreate(BaseModel):
    owner_id: str
    name: str
    description: Optional[str] = None
    county: Optional[str] = None
    town: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    capacity: Optional[int] = None


class VenueOut(BaseModel):
    venue_id: str
    name: str
    county: Optional[str]
    town: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# ---- DJs ----
class DJCreate(BaseModel):
    user_id: str
    stage_name: str
    genres: Optional[str] = None
    bio: Optional[str] = None
    base_fee: Decimal = Decimal("0")
    mpesa_payout_number: Optional[str] = None


class DJOut(BaseModel):
    dj_id: str
    stage_name: str
    genres: Optional[str]
    base_fee: Decimal
    rating: Decimal

    class Config:
        from_attributes = True


# ---- Events ----
class EventCreate(BaseModel):
    venue_id: str
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    ticket_price: Decimal
    ticket_capacity: int = 0


class EventOut(BaseModel):
    event_id: str
    title: str
    ticket_price: Decimal
    ticket_capacity: int
    tickets_sold: int
    status: str

    class Config:
        from_attributes = True


# ---- Song requests ----
class SongRequestCreate(BaseModel):
    user_id: str
    event_id: str
    dj_id: str
    song_title: str
    artist_name: Optional[str] = None
    tip_amount: Decimal = Decimal("0")


class SongRequestOut(BaseModel):
    request_id: str
    song_title: str
    tip_amount: Decimal
    platform_fee: Decimal
    dj_payout: Decimal
    status: str

    class Config:
        from_attributes = True


# ---- Tips ----
class TipCreate(BaseModel):
    user_id: str
    recipient_type: str
    recipient_id: str
    event_id: Optional[str] = None
    song_request_id: Optional[str] = None
    gross_amount: Decimal


class TipOut(BaseModel):
    tip_id: str
    gross_amount: Decimal
    platform_fee: Decimal
    net_amount: Decimal
    status: str

    class Config:
        from_attributes = True


# ---- Tickets ----
class TicketCreate(BaseModel):
    event_id: str
    buyer_id: str
    ticket_type: str = "regular"


class TicketOut(BaseModel):
    ticket_id: str
    price: Decimal
    platform_fee: Decimal
    artist_payout: Decimal
    qr_code: str
    status: str

    class Config:
        from_attributes = True


# ---- Table reservations ----
class TableReservationCreate(BaseModel):
    venue_id: str
    user_id: str
    event_id: Optional[str] = None
    table_number: str
    party_size: int
    reservation_fee: Decimal
    reserved_for: Optional[datetime] = None


class TableReservationOut(BaseModel):
    reservation_id: str
    table_number: str
    party_size: int
    reservation_fee: Decimal
    platform_fee: Decimal
    venue_payout: Decimal
    status: str

    class Config:
        from_attributes = True

class SongRequestStatusUpdate(BaseModel):
    status: str   # accepted | playing | played | rejected
    queue_position: Optional[int] = None


class EarningsOut(BaseModel):
    earned: Decimal
    committed: Decimal
    available: Decimal


class PayoutCreate(BaseModel):
    amount: Decimal
    notes: Optional[str] = None


class PayoutOut(BaseModel):
    payout_id: str
    recipient_type: str
    recipient_id: str
    amount: Decimal
    status: str
    requested_at: datetime
    approved_at: Optional[datetime]
    paid_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ReservationStatusUpdate(BaseModel):
    status: str   # confirmed | cancelled | no_show