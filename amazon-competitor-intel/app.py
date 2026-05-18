"""
Amazon Competitor Intelligence System - Phase 1
Flask API triggered by Make.com schedule
"""
import os
import traceback
from datetime import datetime
from flask import Flask, jsonify, request

from rainforest import get_product_data
from sheets import (
    get_asin_list, get_all_history,
    append_product_history, append_alert, write_ai_summary
)
from analyzer import detect_changes
from ai_summary import generate_summary

app = Flask(__name__)


def _check_secret():
    secret = request.headers.get("X-Secret-Key", "")
    return secret == os.environ.get("WEBHOOK_SECRET", "")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/run-monitor", methods=["POST"])
def run_monitor():
    if not _check_secret():
        return jsonify({"error": "Unauthorized"}), 401

    asins = get_asin_list()
    history = get_all_history()
    all_alerts = []
    products_summary = []
    errors = []

    for item in asins:
        asin = item["ASIN"]
        threshold = float(item.get("Alert_Threshold_Pct", 5.0))

        try:
            current = get_product_data(asin)

            rows = history.get(asin, [])  # ← 从内存取，不再读 Sheet
            last = rows[-1] if rows else None

            # Detect changes vs last snapshot
            alerts = detect_changes(current, last, threshold)
            all_alerts.extend(alerts)

            # Persist snapshot
            append_product_history({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "asin": asin,
                "title": current.get("title", ""),
                "price": current.get("price", ""),
                "rating": current.get("rating", ""),
                "reviews_count": current.get("reviews_count", ""),
                "bsr": current.get("bsr", ""),
            })

            # Persist individual alerts
            for alert in alerts:
                append_alert(alert)

            products_summary.append({
                "asin": asin,
                "title": current.get("title", ""),
                "price": current.get("price"),
                "rating": current.get("rating"),
                "bsr": current.get("bsr"),
            })

        except Exception as e:
            print(f"[ERROR] ASIN {asin}: {e}")
            traceback.print_exc()
            errors.append({"asin": asin, "error": str(e)})

    # AI daily summary
    ai_summary = ""
    try:
        ai_summary = generate_summary(all_alerts, products_summary)
        write_ai_summary(ai_summary)
    except Exception as e:
        print(f"[ERROR] AI summary failed: {e}")
        ai_summary = "AI summary unavailable."

    return jsonify({
        "status": "success",
        "run_at": datetime.now().isoformat(),
        "asins_processed": len(products_summary),
        "alerts_count": len(all_alerts),
        "alerts": all_alerts,
        "ai_summary": ai_summary,
        "errors": errors,
    })


@app.route("/snapshot/<asin>", methods=["GET"])
def snapshot(asin):
    """Manual single-ASIN fetch for testing."""
    if not _check_secret():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = get_product_data(asin)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
