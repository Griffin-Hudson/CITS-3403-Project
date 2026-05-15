"""Wallet operations — keeps balance/earnings updates and ledger writes together
so callers can't update a user's funds without recording a Transaction."""

from app.models import db, Purchase, Transaction

# ---------------------------------------------------------------------------
# Tier + payment-method constants (used by checkout flow)
# ---------------------------------------------------------------------------

TIER_LEASE     = 'lease'
TIER_PREMIUM   = 'premium'
TIER_EXCLUSIVE = 'exclusive'

METHOD_BALANCE = 'balance'
METHOD_CARD    = 'card'

TIER_LABELS = {
    TIER_LEASE:     'Lease',
    TIER_PREMIUM:   'Premium',
    TIER_EXCLUSIVE: 'Exclusive',
}


def tier_price(beat, tier):
    """Return the price for `tier` on `beat`, or None if the tier is not offered."""
    if tier == TIER_LEASE:
        return beat.price
    if tier == TIER_PREMIUM:
        return beat.premium_price
    if tier == TIER_EXCLUSIVE:
        return beat.exclusive_price
    return None


def user_owns_tier(user, beat, tier):
    """True if `user` already holds this tier on `beat`."""
    if not user or not user.is_authenticated:
        return False
    return Purchase.query.filter_by(
        buyer_id=user.id, beat_id=beat.id, licence_type=tier
    ).first() is not None


def beat_has_exclusive_owner(beat):
    """True if the exclusive tier on `beat` has already been sold."""
    return Purchase.query.filter_by(
        beat_id=beat.id, licence_type=TIER_EXCLUSIVE
    ).first() is not None


def purchase_beat(buyer, beat, tier, method):
    """Write a Purchase row plus matching ledger entries for a completed checkout.

    Balance method deducts funds; card is demo-only and skips the deduction
    but still records a transaction so My Feeds and producer earnings reflect
    the sale. Caller must call db.session.commit() after.
    """
    price = tier_price(beat, tier)
    label = TIER_LABELS.get(tier, tier)
    note  = f'{label} licence — "{beat.title}"'

    if method == METHOD_BALANCE:
        record_purchase(buyer, price, note=note)
    else:
        # card (demo): no real charge, but log so it appears in wallet history
        db.session.add(Transaction(
            user_id=buyer.id,
            type=Transaction.TYPE_PURCHASE,
            amount=price,
            balance_after=buyer.balance or 0.0,
            note=f'{note} (card demo)',
        ))

    if beat.producer_id and beat.producer_id != buyer.id and beat.producer:
        record_earning(beat.producer, price, note=f'Sale — "{beat.title}" ({label})')

    purchase = Purchase(
        buyer_id=buyer.id,
        beat_id=beat.id,
        price_paid=price,
        licence_type=tier,
    )
    db.session.add(purchase)
    return purchase


# ---------------------------------------------------------------------------
# Primitive ledger operations (used directly by routes and purchase_beat above)
# ---------------------------------------------------------------------------

def top_up(user, amount, note=None):
    """Add `amount` to the user's wallet balance and record a topup transaction."""
    user.balance = (user.balance or 0.0) + amount
    tx = Transaction(
        user_id=user.id,
        type=Transaction.TYPE_TOPUP,
        amount=amount,
        balance_after=user.balance,
        note=note,
    )
    db.session.add(tx)
    return tx


def record_purchase(user, amount, note=None):
    """Deduct `amount` from the user's balance and record a purchase transaction."""
    user.balance = (user.balance or 0.0) - amount
    tx = Transaction(
        user_id=user.id,
        type=Transaction.TYPE_PURCHASE,
        amount=amount,
        balance_after=user.balance,
        note=note,
    )
    db.session.add(tx)
    return tx


def record_earning(producer, amount, note=None):
    """Credit `amount` to a producer's lifetime earnings and wallet balance."""
    producer.earnings = (producer.earnings or 0.0) + amount
    producer.balance = (producer.balance or 0.0) + amount
    tx = Transaction(
        user_id=producer.id,
        type=Transaction.TYPE_EARNING,
        amount=amount,
        balance_after=producer.balance,
        note=note,
    )
    db.session.add(tx)
    return tx
