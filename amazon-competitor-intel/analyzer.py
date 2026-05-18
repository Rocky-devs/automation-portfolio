"""
Change detection logic.
Compares current snapshot vs last stored row and returns a list of alert dicts.

Alert priority matrix:
  HIGH   → price drop, rating drop, massive BSR improvement (competitor gaining)
  MEDIUM → price increase, BSR worsening significantly, large review spike
  LOW    → minor rating increase, small review growth
"""
from datetime import datetime


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def detect_changes(current: dict, last: dict | None, price_threshold_pct: float = 5.0) -> list[dict]:
    """
    current   - fresh data from Rainforest API
    last      - last row from Product_History (keys: Price, Rating, Reviews_Count, BSR)
    price_threshold_pct - minimum % price move to trigger alert (default 5%)

    Returns list of alert dicts.
    """
    if last is None:
        return []  # First run for this ASIN — no baseline to compare

    alerts = []
    asin = current["asin"]
    ts = _now()

    # ── Price ─────────────────────────────────────────────────────────────
    try:
        old_price = float(last["Price"])
        new_price = float(current["price"])
        if old_price > 0 and new_price > 0:
            change_pct = (new_price - old_price) / old_price * 100
            if abs(change_pct) >= price_threshold_pct:
                alerts.append({
                    "timestamp": ts,
                    "asin": asin,
                    "type": "PRICE_DROP" if change_pct < 0 else "PRICE_INCREASE",
                    "old_value": old_price,
                    "new_value": new_price,
                    "change_pct": round(change_pct, 2),
                    "priority": "HIGH" if change_pct < 0 else "MEDIUM",
                })
    except (TypeError, ValueError, KeyError):
        pass

    # ── Rating ────────────────────────────────────────────────────────────
    try:
        old_rating = float(last["Rating"])
        new_rating = float(current["rating"])
        delta = new_rating - old_rating
        if abs(delta) >= 0.1:
            alerts.append({
                "timestamp": ts,
                "asin": asin,
                "type": "RATING_DROP" if delta < 0 else "RATING_RISE",
                "old_value": old_rating,
                "new_value": new_rating,
                "change_pct": round(delta, 2),
                "priority": "HIGH" if delta < 0 else "LOW",
            })
    except (TypeError, ValueError, KeyError):
        pass

    # ── Review count ──────────────────────────────────────────────────────
    try:
        old_reviews = int(last["Reviews_Count"])
        new_reviews = int(current["reviews_count"])
        delta = new_reviews - old_reviews
        # Trigger if growth >= 10 reviews or >= 2% whichever is smaller
        pct_delta = delta / old_reviews * 100 if old_reviews > 0 else 0
        if delta >= 10 or abs(pct_delta) >= 2:
            alerts.append({
                "timestamp": ts,
                "asin": asin,
                "type": "REVIEW_SPIKE" if delta > 0 else "REVIEW_DROP",
                "old_value": old_reviews,
                "new_value": new_reviews,
                "change_pct": delta,          # absolute delta for reviews
                "priority": "MEDIUM",
            })
    except (TypeError, ValueError, KeyError):
        pass

    # ── BSR ───────────────────────────────────────────────────────────────
    try:
        old_bsr = int(last["BSR"])
        new_bsr = int(current["bsr"])
        if old_bsr > 0:
            change_pct = (new_bsr - old_bsr) / old_bsr * 100
            # BSR improves when number goes DOWN
            if abs(change_pct) >= 20:
                alerts.append({
                    "timestamp": ts,
                    "asin": asin,
                    "type": "BSR_IMPROVE" if new_bsr < old_bsr else "BSR_DECLINE",
                    "old_value": old_bsr,
                    "new_value": new_bsr,
                    "change_pct": round(change_pct, 2),
                    # Competitor gaining ground (BSR improves) = HIGH for seller
                    "priority": "HIGH" if new_bsr < old_bsr else "MEDIUM",
                })
    except (TypeError, ValueError, KeyError):
        pass

    return alerts
