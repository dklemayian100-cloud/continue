from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from . import models, schemas
from .security import get_current_user
from .payouts import dj_earnings, venue_earnings
from .mpesa import b2c_payout

router = APIRouter(tags=["dashboards"])


# ---------- helpers ----------
def _current_dj(db: Session, user: models.User) -> models.DJ:
    dj = db.query(models.DJ).filter_by(user_id=user.user_id).first()
    if not dj:
        raise HTTPException(403, "No DJ profile for this user")
    return dj


def _current_venue(db: Session, user: models.User, venue_id: str) -> models.Venue:
    venue = db.get(models.Venue, venue_id)
    if not venue:
        raise HTTPException(404, "Venue not found")
    if venue.owner_id != user.user_id and user.role != "admin":
        raise HTTPException(403, "Not your venue")
    return venue


def _require_admin(user: models.User):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")


# =========================================================
# DJ dashboard
# =========================================================
@router.get("/dj/me/queue", response_model=list[schemas.SongRequestOut])
def my_queue(
    status: str | None = None,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    dj = _current_dj(db, current)
    q = db.query(models.SongRequest).filter(models.SongRequest.dj_id == dj.dj_id)
    if status:
        q = q.filter(models.SongRequest.status == status)
    # highest tip first, then oldest
    q = q.order_by(
        models.SongRequest.tip_amount.desc(),
        models.SongRequest.created_at.asc(),
    )
    return q.all()


@router.patch("/dj/me/queue/{request_id}", response_model=schemas.SongRequestOut)
def update_request_status(
    request_id: str,
    payload: schemas.SongRequestStatusUpdate,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    dj = _current_dj(db, current)
    sr = db.get(models.SongRequest, request_id)
    if not sr or sr.dj_id != dj.dj_id:
        raise HTTPException(404, "Request not found for this DJ")
    if payload.status not in ("accepted", "playing", "played", "rejected"):
        raise HTTPException(400, "Invalid status")

    sr.status = payload.status
    if payload.queue_position is not None:
        sr.queue_position = payload.queue_position
    db.commit()
    db.refresh(sr)
    return sr


@router.get("/dj/me/earnings", response_model=schemas.EarningsOut)
def my_dj_earnings(
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    dj = _current_dj(db, current)
    return dj_earnings(db, dj.dj_id)


@router.post("/dj/me/payouts", response_model=schemas.PayoutOut)
def request_dj_payout(
    payload: schemas.PayoutCreate,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    dj = _current_dj(db, current)
    balances = dj_earnings(db, dj.dj_id)
    amount = Decimal(payload.amount)
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    if amount > balances["available"]:
        raise HTTPException(
            400, f"Insufficient balance. Available: {balances['available']}"
        )
    payout = models.Payout(
        recipient_type="dj",
        recipient_id=dj.dj_id,
        amount=amount,
        status="requested",
        notes=payload.notes,
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


# =========================================================
# Venue dashboard
# =========================================================
@router.get("/venues/{venue_id}/reservations",
            response_model=list[schemas.TableReservationOut])
def venue_reservations(
    venue_id: str,
    status: str | None = None,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    venue = _current_venue(db, current, venue_id)
    q = db.query(models.TableReservation).filter_by(venue_id=venue.venue_id)
    if status:
        q = q.filter(models.TableReservation.status == status)
    return q.order_by(models.TableReservation.created_at.desc()).all()


@router.patch("/venues/{venue_id}/reservations/{reservation_id}",
              response_model=schemas.TableReservationOut)
def update_reservation(
    venue_id: str,
    reservation_id: str,
    payload: schemas.ReservationStatusUpdate,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    venue = _current_venue(db, current, venue_id)
    res = db.get(models.TableReservation, reservation_id)
    if not res or res.venue_id != venue.venue_id:
        raise HTTPException(404, "Reservation not found")
    if payload.status not in ("confirmed", "cancelled", "no_show"):
        raise HTTPException(400, "Invalid status")
    res.status = payload.status
    db.commit()
    db.refresh(res)
    return res


@router.get("/venues/{venue_id}/events",
            response_model=list[schemas.EventOut])
def venue_events(
    venue_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    venue = _current_venue(db, current, venue_id)
    return (
        db.query(models.Event)
        .filter_by(venue_id=venue.venue_id)
        .order_by(models.Event.start_time.desc())
        .all()
    )


@router.get("/venues/{venue_id}/earnings", response_model=schemas.EarningsOut)
def my_venue_earnings(
    venue_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    venue = _current_venue(db, current, venue_id)
    return venue_earnings(db, venue.venue_id)


@router.post("/venues/{venue_id}/payouts", response_model=schemas.PayoutOut)
def request_venue_payout(
    venue_id: str,
    payload: schemas.PayoutCreate,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    venue = _current_venue(db, current, venue_id)
    balances = venue_earnings(db, venue.venue_id)
    amount = Decimal(payload.amount)
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    if amount > balances["available"]:
        raise HTTPException(
            400, f"Insufficient balance. Available: {balances['available']}"
        )
    payout = models.Payout(
        recipient_type="venue",
        recipient_id=venue.venue_id,
        amount=amount,
        status="requested",
        notes=payload.notes,
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


# =========================================================
# Admin payout management
# =========================================================
@router.get("/admin/payouts", response_model=list[schemas.PayoutOut])
def list_payouts(
    status: str | None = None,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    _require_admin(current)
    q = db.query(models.Payout)
    if status:
        q = q.filter(models.Payout.status == status)
    return q.order_by(models.Payout.requested_at.desc()).all()


@router.post("/admin/payouts/{payout_id}/approve",
             response_model=schemas.PayoutOut)
def approve_payout(
    payout_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    _require_admin(current)
    payout = db.get(models.Payout, payout_id)
    if not payout:
        raise HTTPException(404, "Payout not found")
    if payout.status != "requested":
        raise HTTPException(400, f"Cannot approve a payout in status {payout.status}")
    payout.status = "approved"
    payout.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(payout)
    return payout


@router.post("/admin/payouts/{payout_id}/reject",
             response_model=schemas.PayoutOut)
def reject_payout(
    payout_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    _require_admin(current)
    payout = db.get(models.Payout, payout_id)
    if not payout:
        raise HTTPException(404, "Payout not found")
    if payout.status != "requested":
        raise HTTPException(400, "Only requested payouts can be rejected")
    payout.status = "rejected"
    payout.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(payout)
    return payout


@router.post("/admin/payouts/{payout_id}/pay", response_model=schemas.PayoutOut)
def pay_payout(
    payout_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """Execute an approved payout via M-Pesa B2C."""
    _require_admin(current)
    payout = db.get(models.Payout, payout_id)
    if not payout:
        raise HTTPException(404, "Payout not found")
    if payout.status != "approved":
        raise HTTPException(400, "Payout must be approved before paying")

    # Resolve recipient phone
    if payout.recipient_type == "dj":
        dj = db.get(models.DJ, payout.recipient_id)
        phone = dj.mpesa_payout_number if dj else None
    else:
        venue = db.get(models.Venue, payout.recipient_id)
        owner = db.get(models.User, venue.owner_id) if venue else None
        phone = owner.mpesa_number if owner else None

    if not phone:
        raise HTTPException(400, "Recipient has no M-Pesa number on file")

    # Call B2C (will fail with dummy creds; safe for testing logic)
    try:
        resp = b2c_payout(
            phone=phone,
            amount=int(payout.amount),
            remarks=f"Payout {payout.payout_id[:8]}",
            occasion="Aluta payout",
        )
        payout.mpesa_conversation_id = resp.get("ConversationID")
        payout.mpesa_originator_id = resp.get("OriginatorConversationID")
        payout.status = "paid"
        payout.paid_at = datetime.utcnow()
    except Exception as exc:
        # Keep status as approved, record the reason for admin retry
        payout.notes = f"{payout.notes or ''}\nB2C failed: {exc}".strip()
    db.commit()
    db.refresh(payout)
    return payout


@router.post("/mpesa/b2c/result")
def b2c_result(payload: dict):
    # Production: verify signature, mark payout paid/failed by ConversationID
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/mpesa/b2c/timeout")
def b2c_timeout(payload: dict):
    return {"ResultCode": 0, "ResultDesc": "Accepted"}