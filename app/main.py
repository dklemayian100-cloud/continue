from decimal import Decimal

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import models, schemas
from .commissions import (
    ticket_split, song_request_split, table_reservation_split,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Aluta-style Nightlife API", version="0.1.0")


# ---------- Users ----------
@app.post("/users", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(phone_number=payload.phone_number).first():
        raise HTTPException(400, "Phone number already registered")
    user = models.User(
        phone_number=payload.phone_number,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=payload.password,  # NOTE: hash this in production
        role=payload.role,
        county=payload.county,
        town=payload.town,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------- Venues ----------
@app.post("/venues", response_model=schemas.VenueOut)
def create_venue(payload: schemas.VenueCreate, db: Session = Depends(get_db)):
    venue = models.Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@app.get("/venues", response_model=list[schemas.VenueOut])
def list_venues(county: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Venue).filter(models.Venue.is_active == True)
    if county:
        q = q.filter(models.Venue.county == county)
    return q.all()


# ---------- DJs ----------
@app.post("/djs", response_model=schemas.DJOut)
def create_dj(payload: schemas.DJCreate, db: Session = Depends(get_db)):
    dj = models.DJ(**payload.model_dump())
    db.add(dj)
    db.commit()
    db.refresh(dj)
    return dj


# ---------- Events ----------
@app.post("/events", response_model=schemas.EventOut)
def create_event(payload: schemas.EventCreate, db: Session = Depends(get_db)):
    event = models.Event(**payload.model_dump(), status="live")
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ---------- Tickets (4% commission) ----------
@app.post("/events/{event_id}/tickets", response_model=schemas.TicketOut)
def buy_ticket(
    event_id: str,
    buyer_id: str,
    ticket_type: str = "regular",
    db: Session = Depends(get_db),
):
    event = db.get(models.Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.ticket_capacity and event.tickets_sold >= event.ticket_capacity:
        raise HTTPException(400, "Event sold out")

    price = Decimal(event.ticket_price)
    platform_fee, artist_payout = ticket_split(price)

    ticket = models.Ticket(
        event_id=event_id,
        buyer_id=buyer_id,
        ticket_type=ticket_type,
        price=price,
        platform_fee=platform_fee,
        artist_payout=artist_payout,
    )
    event.tickets_sold += 1
    if event.ticket_capacity and event.tickets_sold >= event.ticket_capacity:
        event.status = "sold_out"

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


# ---------- Song requests (5% or flat fee on tip) ----------
@app.post("/song-requests", response_model=schemas.SongRequestOut)
def create_song_request(payload: schemas.SongRequestCreate, db: Session = Depends(get_db)):
    platform_fee, dj_payout = song_request_split(payload.tip_amount)

    sr = models.SongRequest(
        **payload.model_dump(),
        platform_fee=platform_fee,
        dj_payout=dj_payout,
        status="pending",
    )
    db.add(sr)
    db.commit()
    db.refresh(sr)
    return sr


# ---------- Tips ----------
@app.post("/tips", response_model=schemas.TipOut)
def create_tip(payload: schemas.TipCreate, db: Session = Depends(get_db)):
    # Reuse song-request split for tips tied to requests; otherwise a flat 5%
    from .commissions import _q, SONG_REQUEST_FEE_RATE
    gross = Decimal(payload.gross_amount)
    fee = _q(gross * SONG_REQUEST_FEE_RATE)
    net = _q(gross - fee)

    tip = models.Tip(
        **payload.model_dump(),
        platform_fee=fee,
        net_amount=net,
        status="pending",
    )
    db.add(tip)
    db.commit()
    db.refresh(tip)
    return tip


# ---------- Table reservations (10% commission) ----------
@app.post("/table-reservations", response_model=schemas.TableReservationOut)
def create_table_reservation(
    payload: schemas.TableReservationCreate, db: Session = Depends(get_db)
):
    fee = Decimal(payload.reservation_fee)
    platform_fee, venue_payout = table_reservation_split(fee)

    res = models.TableReservation(
        **payload.model_dump(),
        platform_fee=platform_fee,
        venue_payout=venue_payout,
        status="pending",
    )
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


@app.get("/health")
def health():
    return {"status": "ok"}