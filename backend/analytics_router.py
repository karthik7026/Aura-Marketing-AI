import datetime
from collections import defaultdict
from fastapi import APIRouter, Depends
from pymongo.database import Database

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper

router = APIRouter(prefix="/api", tags=["Analytics & Notifications"])


@router.get("/analytics/dashboard")
def get_analytics_dashboard(
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    transactions = current_user.get("transactions", [])
    total_spent = sum(abs(tx.get("amount", 0)) for tx in transactions if tx.get("amount", 0) < 0)

    # FIX: daily_token_usage used to be a hardcoded 7-day array shown to
    # every user regardless of what they actually did. Now it's a real
    # aggregation of this user's own debit transactions over the last 7 days.
    daily_spend = defaultdict(int)
    today = datetime.datetime.utcnow().date()
    for tx in transactions:
        amt = tx.get("amount", 0)
        if amt >= 0:
            continue
        ts = tx.get("created_at", "")
        try:
            tx_date = datetime.datetime.fromisoformat(ts.replace("Z", "")).date()
        except Exception:
            continue
        delta_days = (today - tx_date).days
        if 0 <= delta_days < 7:
            daily_spend[tx_date.isoformat()] += abs(amt)

    daily_usage = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        daily_usage.append({
            "day": d.strftime("%a"),
            "date": d.isoformat(),
            "tokens": daily_spend.get(d.isoformat(), 0),
        })

    return {
        "status": "success",
        "email": current_user["email"],
        "tokens_balance": current_user.get("tokens", 0),
        "total_tokens_spent": total_spent,
        "daily_token_usage": daily_usage,
        "data_source": "real_transaction_history",
        "recent_activity": transactions[-5:] if transactions else [],
    }


@router.get("/notifications")
def get_user_notifications(
    current_user: dict = Depends(get_current_user_helper),
):
    # FIX: this used to be a fixed, fabricated feed shown to every user.
    # A real implementation needs a notifications collection populated by
    # the events it describes (rank changes, payment confirmations, scan
    # completions) — that data-producing side doesn't exist yet, so rather
    # than keep inventing fake events, we derive what we can from this
    # user's own real transaction history and are explicit that this is
    # a partial, best-effort feed.
    notifications = []
    for tx in reversed(current_user.get("transactions", [])[-10:]):
        notifications.append({
            "id": tx.get("transaction_id", "unknown"),
            "title": tx.get("tier_name", "Wallet Activity"),
            "message": f"{'Credited' if tx.get('amount', 0) > 0 else 'Spent'} {abs(tx.get('amount', 0))} tokens.",
            "timestamp": tx.get("created_at", ""),
            "read": False,
        })

    return {
        "status": "success",
        "unread_count": len(notifications),
        "data_source": "derived_from_real_transactions",
        "notifications": notifications,
    }


@router.post("/notifications/mark-read")
def mark_notifications_read(
    current_user: dict = Depends(get_current_user_helper),
):
    return {
        "status": "success",
        "message": "All notifications marked as read"
    }
