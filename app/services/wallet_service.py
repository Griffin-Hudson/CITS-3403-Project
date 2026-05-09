"""Wallet operations — keep balance/earnings updates and ledger writes in one place
so callers can't accidentally update a user's funds without recording a Transaction."""

from app.models import db, Transaction


def top_up(user, amount, note=None):
    """Add `amount` to the user's wallet balance and record a topup transaction.

    Returns the created Transaction. Does not commit — caller controls the txn boundary.
    """
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
    """Deduct `amount` from the user's balance and record a purchase transaction.

    Returns the created Transaction. Caller controls commit and is responsible
    for checking the user has enough balance before calling.
    """
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
    """Credit `amount` to a producer's lifetime earnings AND wallet balance,
    then record an earning transaction.

    Returns the created Transaction. Caller controls commit.
    """
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
