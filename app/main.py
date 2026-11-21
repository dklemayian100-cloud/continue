from decimal import Decimal

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from . import models, schemas
from .auth import router as auth_router
from .security import hash_password, get_current_user
from .commissions import (
    ticket_split, song_request_split, table_reservation_split, record_ledger,
)
from .mpesa import stk_push
import qrcode
import io
from fastapi.responses import StreamingResponse
from .dashboard import router as dashboard_router

app = FastAPI(title="Aluta-style Nightlife API", version="0.2.0")
app.include_router(auth_router)
app.include_router(dashboard_router)


# ---------- Users ----------
@app.post("/users", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(phone_number=payload.phone_number).first():
        raise HTTPException(400, "Phone number already registered")
    user = models.User(
        phone_number=payload.phone_number,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        county=payload.county,
        town=payload.town,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/me", response_model=schemas.UserOut)
def me(current: models.User = Depends(get_current_user)):
    return current


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


# ---------- Tickets (4% commission + ledger) ----------
@app.post("/events/{event_id}/tickets", response_model=schemas.TicketOut)
def buy_ticket(
    event_id: str,
    ticket_type: str = "regular",
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
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
        buyer_id=current.user_id,
        ticket_type=ticket_type,
        price=price,
        platform_fee=platform_fee,
        artist_payout=artist_payout,
    )
    event.tickets_sold += 1
    if event.ticket_capacity and event.tickets_sold >= event.ticket_capacity:
        event.status = "sold_out"

    db.add(ticket)
    db.flush()  # populate ticket.ticket_id before ledger
    record_ledger(
        db,
        reference_type="ticket",
        reference_id=ticket.ticket_id,
        gross=price,
        platform_fee=platform_fee,
        net_to_recipient=artist_payout,
        recipient_id=event.venue_id,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


# ---------- Ticket QR code ----------
@app.get("/tickets/{ticket_id}/qr")
def ticket_qr(
    ticket_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    ticket = db.get(models.Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if ticket.buyer_id != current.user_id and current.role != "admin":
        raise HTTPException(403, "Not your ticket")

    img = qrcode.make(ticket.qr_code)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


# ---------- Song requests ----------
@app.post("/song-requests", response_model=schemas.SongRequestOut)
def create_song_request(
    payload: schemas.SongRequestCreate,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    platform_fee, dj_payout = song_request_split(payload.tip_amount)

    sr = models.SongRequest(
        user_id=current.user_id,
        event_id=payload.event_id,
        dj_id=payload.dj_id,
        song_title=payload.song_title,
        artist_name=payload.artist_name,
        tip_amount=payload.tip_amount,
        platform_fee=platform_fee,
        dj_payout=dj_payout,
        status="pending",
    )
    db.add(sr)
    db.flush()
    if payload.tip_amount and payload.tip_amount > 0:
        record_ledger(
            db,
            reference_type="tip",
            reference_id=sr.request_id,
            gross=Decimal(payload.tip_amount),
            platform_fee=platform_fee,
            net_to_recipient=dj_payout,
            recipient_id=payload.dj_id,
        )
    db.commit()
    db.refresh(sr)
    return sr


# ---------- Table reservations ----------
@app.post("/table-reservations", response_model=schemas.TableReservationOut)
def create_table_reservation(
    payload: schemas.TableReservationCreate,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    fee = Decimal(payload.reservation_fee)
    platform_fee, venue_payout = table_reservation_split(fee)

    res = models.TableReservation(
        venue_id=payload.venue_id,
        user_id=current.user_id,
        event_id=payload.event_id,
        table_number=payload.table_number,
        party_size=payload.party_size,
        reservation_fee=fee,
        platform_fee=platform_fee,
        venue_payout=venue_payout,
        status="pending",
        reserved_for=payload.reserved_for,
    )
    db.add(res)
    db.flush()
    record_ledger(
        db,
        reference_type="reservation",
        reference_id=res.reservation_id,
        gross=fee,
        platform_fee=platform_fee,
        net_to_recipient=venue_payout,
        recipient_id=payload.venue_id,
    )
    db.commit()
    db.refresh(res)
    return res


# ---------- M-Pesa STK Push ----------
@app.post("/mpesa/stk-push/{ticket_id}")
def initiate_ticket_payment(
    ticket_id: str,
    phone: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    ticket = db.get(models.Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if ticket.buyer_id != current.user_id:
        raise HTTPException(403, "Not your ticket")

    result = stk_push(
        phone=phone,
        amount=int(ticket.price),
        account_ref=ticket.ticket_id[:12],
        description="Aluta ticket",
    )
    return {"stk_response": result}


@app.post("/mpesa/callback")
def mpesa_callback(payload: dict):
    # In production: verify signature, update Ticket.status + Tip.status here
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@app.get("/health")
def health():
    return {"status": "ok"}