import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Numeric, ForeignKey, Enum, Text
)
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=gen_uuid)
    phone_number = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum("customer", "venue_owner", "dj", "admin", name="user_role"),
                  default="customer", nullable=False)
    wallet_balance = Column(Numeric(12, 2), default=0)
    mpesa_number = Column(String, nullable=True)
    county = Column(String, nullable=True)
    town = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dj_profile = relationship("DJ", back_populates="user", uselist=False)
    venues = relationship("Venue", back_populates="owner")
    song_requests = relationship("SongRequest", back_populates="user")
    tips = relationship("Tip", back_populates="user")
    tickets = relationship("Ticket", back_populates="buyer")
    reservations = relationship("TableReservation", back_populates="user")


class Venue(Base):
    __tablename__ = "venues"

    venue_id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    county = Column(String, nullable=True)
    town = Column(String, nullable=True)
    address = Column(String, nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    capacity = Column(Integer, nullable=True)
    commission_rate_override = Column(Numeric(5, 4), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="venues")
    events = relationship("Event", back_populates="venue")
    reservations = relationship("TableReservation", back_populates="venue")


class DJ(Base):
    __tablename__ = "djs"

    dj_id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.user_id"), unique=True, nullable=False)
    stage_name = Column(String, nullable=False)
    genres = Column(String, nullable=True)  # comma-separated
    bio = Column(Text, nullable=True)
    base_fee = Column(Numeric(12, 2), default=0)
    rating = Column(Numeric(3, 2), default=0)
    is_verified = Column(Boolean, default=False)
    mpesa_payout_number = Column(String, nullable=True)

    user = relationship("User", back_populates="dj_profile")
    song_requests = relationship("SongRequest", back_populates="dj")


class Event(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, default=gen_uuid)
    venue_id = Column(String, ForeignKey("venues.venue_id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    ticket_price = Column(Numeric(12, 2), nullable=False, default=0)
    ticket_capacity = Column(Integer, default=0)
    tickets_sold = Column(Integer, default=0)
    status = Column(Enum("draft", "live", "sold_out", "cancelled", name="event_status"),
                    default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)

    venue = relationship("Venue", back_populates="events")
    tickets = relationship("Ticket", back_populates="event")
    song_requests = relationship("SongRequest", back_populates="event")
    reservations = relationship("TableReservation", back_populates="event")


class SongRequest(Base):
    __tablename__ = "song_requests"

    request_id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=False)
    dj_id = Column(String, ForeignKey("djs.dj_id"), nullable=False)
    song_title = Column(String, nullable=False)
    artist_name = Column(String, nullable=True)
    tip_amount = Column(Numeric(12, 2), default=0)
    platform_fee = Column(Numeric(12, 2), default=0)
    dj_payout = Column(Numeric(12, 2), default=0)
    status = Column(Enum("pending", "accepted", "playing", "played", "rejected",
                         name="song_request_status"), default="pending")
    queue_position = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="song_requests")
    event = relationship("Event", back_populates="song_requests")
    dj = relationship("DJ", back_populates="song_requests")


class Tip(Base):
    __tablename__ = "tips"

    tip_id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    recipient_type = Column(Enum("dj", "venue", "performer", name="recipient_type"),
                            nullable=False)
    recipient_id = Column(String, nullable=False)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=True)
    song_request_id = Column(String, ForeignKey("song_requests.request_id"), nullable=True)
    gross_amount = Column(Numeric(12, 2), nullable=False)
    platform_fee = Column(Numeric(12, 2), default=0)
    net_amount = Column(Numeric(12, 2), default=0)
    mpesa_transaction_id = Column(String, nullable=True)
    status = Column(Enum("pending", "completed", "failed", "refunded", name="tip_status"),
                    default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tips")


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(String, primary_key=True, default=gen_uuid)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=False)
    buyer_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    ticket_type = Column(Enum("regular", "vip", "early_bird", name="ticket_type"),
                         default="regular")
    price = Column(Numeric(12, 2), nullable=False)
    platform_fee = Column(Numeric(12, 2), default=0)
    artist_payout = Column(Numeric(12, 2), default=0)
    qr_code = Column(String, unique=True, default=gen_uuid)
    status = Column(Enum("valid", "used", "cancelled", "refunded", name="ticket_status"),
                    default="valid")
    purchased_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="tickets")
    buyer = relationship("User", back_populates="tickets")


class TableReservation(Base):
    __tablename__ = "table_reservations"

    reservation_id = Column(String, primary_key=True, default=gen_uuid)
    venue_id = Column(String, ForeignKey("venues.venue_id"), nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=True)
    table_number = Column(String, nullable=False)
    party_size = Column(Integer, nullable=False)
    reservation_fee = Column(Numeric(12, 2), nullable=False)
    platform_fee = Column(Numeric(12, 2), default=0)
    venue_payout = Column(Numeric(12, 2), default=0)
    status = Column(Enum("pending", "confirmed", "cancelled", "no_show",
                         name="reservation_status"), default="pending")
    reserved_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    venue = relationship("Venue", back_populates="reservations")
    user = relationship("User", back_populates="reservations")
    event = relationship("Event", back_populates="reservations")