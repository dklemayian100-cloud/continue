from decimal import Decimal, ROUND_HALF_UP

# ---- Configurable rates ----
TICKET_COMMISSION_RATE = Decimal("0.04")          # 4% on artist ticket sales
SONG_REQUEST_FEE_RATE = Decimal("0.05")           # 5% on song-request tips
SONG_REQUEST_FLAT_FEE = Decimal("0")              # set > 0 to use flat fee instead
TABLE_BOOKING_FEE_RATE = Decimal("0.10")          # 10% on table reservations
MERCH_FEE_RATE = Decimal("0.07")                  # 7% on merchandise


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ticket_split(price: Decimal) -> tuple[Decimal, Decimal]:
    price = Decimal(price)
    platform_fee = _q(price * TICKET_COMMISSION_RATE)
    artist_payout = _q(price - platform_fee)
    return platform_fee, artist_payout


def song_request_split(tip_amount: Decimal) -> tuple[Decimal, Decimal]:
    tip_amount = Decimal(tip_amount)
    if SONG_REQUEST_FLAT_FEE > 0:
        platform_fee = _q(SONG_REQUEST_FLAT_FEE)
    else:
        platform_fee = _q(tip_amount * SONG_REQUEST_FEE_RATE)
    if platform_fee > tip_amount:
        platform_fee = tip_amount
    dj_payout = _q(tip_amount - platform_fee)
    return platform_fee, dj_payout


def table_reservation_split(fee: Decimal) -> tuple[Decimal, Decimal]:
    fee = Decimal(fee)
    platform_fee = _q(fee * TABLE_BOOKING_FEE_RATE)
    venue_payout = _q(fee - platform_fee)
    return platform_fee, venue_payout


def merchandise_split(sale_price: Decimal) -> tuple[Decimal, Decimal]:
    sale_price = Decimal(sale_price)
    platform_fee = _q(sale_price * MERCH_FEE_RATE)
    seller_payout = _q(sale_price - platform_fee)
    return platform_fee, seller_payout