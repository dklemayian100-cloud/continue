from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models


def dj_earnings(db: Session, dj_id: str) -> dict:
    """Total earned, total paid out, available balance for a DJ."""
    earned = (
        db.query(func.coalesce(func.sum(models.TransactionLedger.net_to_recipient), 0))
        .filter(
            models.TransactionLedger.recipient_id == dj_id,
            models.TransactionLedger.reference_type == "tip",
        )
        .scalar()
    )
    earned = Decimal(earned or 0)

    requested = (
        db.query(func.coalesce(func.sum(models.Payout.amount), 0))
        .filter(
            models.Payout.recipient_id == dj_id,
            models.Payout.recipient_type == "dj",
            models.Payout.status.in_(["requested", "approved", "paid"]),
        )
        .scalar()
    )
    requested = Decimal(requested or 0)

    return {
        "earned": earned,
        "committed": requested,
        "available": earned - requested,
    }


def venue_earnings(db: Session, venue_id: str) -> dict:
    earned = (
        db.query(func.coalesce(func.sum(models.TransactionLedger.net_to_recipient), 0))
        .filter(
            models.TransactionLedger.recipient_id == venue_id,
            models.TransactionLedger.reference_type.in_(["ticket", "reservation"]),
        )
        .scalar()
    )
    earned = Decimal(earned or 0)

    requested = (
        db.query(func.coalesce(func.sum(models.Payout.amount), 0))
        .filter(
            models.Payout.recipient_id == venue_id,
            models.Payout.recipient_type == "venue",
            models.Payout.status.in_(["requested", "approved", "paid"]),
        )
        .scalar()
    )
    requested = Decimal(requested or 0)

    return {
        "earned": earned,
        "committed": requested,
        "available": earned - requested,
    }