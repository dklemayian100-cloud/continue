from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_db
from . import models, schemas
from .security import get_current_user

router = APIRouter(tags=["waitlist"])

PROMOTION_WINDOW_MINUTES = 10


def _next_position(db: Session, event_id: str) -> int:
    max_pos = (
        db.query(func.coalesce(func.max(models.WaitlistEntry.position), 0))
        .filter(models.WaitlistEntry.event_id == event_id)
        .scalar()
    )
    return int(max_pos or 0) + 1


def _promote_next(db: Session, event_id: str) -> models.WaitlistEntry | None:
    """Promote the earliest 'waiting' entry to 'promoted' with an expiry."""
    entry = (
        db.query(models.WaitlistEntry)
        .filter(
            models.WaitlistEntry.event_id == event_id,
            models.WaitlistEntry.status == "waiting",
        )
        .order_by(models.WaitlistEntry.position.asc())
        .first()
    )
    if not entry:
        return None
    entry.status = "promoted"
    entry.promoted_at = datetime.utcnow()
    entry.expires_at = datetime.utcnow() + timedelta(minutes=PROMOTION_WINDOW_MINUTES)
    return entry


def _expire_stale(db: Session, event_id: str) -> int:
    """Mark promoted entries past their window as expired. Returns count."""
    now = datetime.utcnow()
    stale = (
        db.query(models.WaitlistEntry)
        .filter(
            models.WaitlistEntry.event_id == event_id,
            models.WaitlistEntry.status == "promoted",
            models.WaitlistEntry.expires_at < now,
        )
        .all()
    )
    for e in stale:
        e.status = "expired"
    return len(stale)


@router.post("/events/{event_id}/waitlist", response_model=schemas.WaitlistOut)
def join_waitlist(
    event_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    event = db.get(models.Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.status == "cancelled":
        raise HTTPException(400, "Event cancelled")

    # expire stale promotions before computing queue state
    _expire_stale(db, event_id)

    existing = (
        db.query(models.WaitlistEntry)
        .filter(
            models.WaitlistEntry.event_id == event_id,
            models.WaitlistEntry.user_id == current.user_id,
            models.WaitlistEntry.status.in_(["waiting", "promoted"]),
        )
        .first()
    )
    if existing:
        db.commit()
        return existing

    entry = models.WaitlistEntry(
        event_id=event_id,
        user_id=current.user_id,
        position=_next_position(db, event_id),
        status="waiting",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/events/{event_id}/waitlist/me", response_model=schemas.WaitlistOut)
def my_waitlist_status(
    event_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    _expire_stale(db, event_id)
    entry = (
        db.query(models.WaitlistEntry)
        .filter(
            models.WaitlistEntry.event_id == event_id,
            models.WaitlistEntry.user_id == current.user_id,
        )
        .order_by(models.WaitlistEntry.created_at.desc())
        .first()
    )
    if not entry:
        raise HTTPException(404, "Not on waitlist")
    db.commit()
    return entry


@router.delete("/events/{event_id}/waitlist/me", response_model=schemas.WaitlistOut)
def leave_waitlist(
    event_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    entry = (
        db.query(models.WaitlistEntry)
        .filter(
            models.WaitlistEntry.event_id == event_id,
            models.WaitlistEntry.user_id == current.user_id,
            models.WaitlistEntry.status.in_(["waiting", "promoted"]),
        )
        .first()
    )
    if not entry:
        raise HTTPException(404, "No active waitlist entry")
    entry.status = "cancelled"
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/events/{event_id}/waitlist", response_model=list[schemas.WaitlistOut])
def full_queue(
    event_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """Admin or venue owner only."""
    event = db.get(models.Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    venue = db.get(models.Venue, event.venue_id)
    if current.role != "admin" and (not venue or venue.owner_id != current.user_id):
        raise HTTPException(403, "Admin or venue owner only")

    _expire_stale(db, event_id)
    entries = (
        db.query(models.WaitlistEntry)
        .filter(
            models.WaitlistEntry.event_id == event_id,
            models.WaitlistEntry.status.in_(["waiting", "promoted", "expired"]),
        )
        .order_by(models.WaitlistEntry.position.asc())
        .all()
    )
    db.commit()
    return entries


# ---------- helper used by main.py ----------
def promote_on_cancel(db: Session, event_id: str):
    """Call when a ticket is cancelled to move the next waiter to 'promoted'."""
    return _promote_next(db, event_id)