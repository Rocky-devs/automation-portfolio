"""
Google Sheets interface via gspread + service account.

Sheet structure (create these tabs manually before first run):

  ASIN_List       → ASIN | Product_Name | Alert_Threshold_Pct | Active
  Product_History → Timestamp | ASIN | Title | Price | Rating | Reviews_Count | BSR
  Alerts_Log      → Timestamp | ASIN | Alert_Type | Old_Value | New_Value | Change_Pct | Priority
  AI_Summary      → Timestamp | Summary
"""
import os
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _client():
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")

    if creds_path:
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    else:
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)

    return gspread.authorize(creds)


def _worksheet(tab_name: str):
    gc = _client()
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    return gc.open_by_key(spreadsheet_id).worksheet(tab_name)


# ──────────────────────────────────────────────
# READ
# ──────────────────────────────────────────────

def get_asin_list() -> list[dict]:
    """Return rows from ASIN_List where Active == Y."""
    ws = _worksheet("ASIN_List")
    rows = ws.get_all_records()
    return [r for r in rows if str(r.get("Active", "")).strip().upper() == "Y"]


def get_all_history() -> dict[str, list]:
    ws = _worksheet("Product_History")
    all_rows = ws.get_all_records()

    grouped = {}
    for row in all_rows:
        asin = str(row.get("ASIN", "")).strip()
        if asin:
            grouped.setdefault(asin, []).append(row)

    # 按时间戳排序，确保最后一个是最新的
    for asin in grouped:
        grouped[asin].sort(key=lambda r: str(r.get("Timestamp", "")))

    return grouped

# ──────────────────────────────────────────────
# WRITE
# ──────────────────────────────────────────────

def append_product_history(row: dict) -> None:
    """
    row keys: timestamp, asin, title, price, rating, reviews_count, bsr
    Column order must match sheet header row.
    """
    ws = _worksheet("Product_History")
    ws.append_row([
        row["timestamp"],
        row["asin"],
        row.get("title", ""),
        row.get("price", ""),
        row.get("rating", ""),
        row.get("reviews_count", ""),
        row.get("bsr", ""),
    ])


def append_alert(alert: dict) -> None:
    """
    alert keys: timestamp, asin, type, old_value, new_value, change_pct, priority
    """
    ws = _worksheet("Alerts_Log")
    ws.append_row([
        alert["timestamp"],
        alert["asin"],
        alert["type"],
        alert["old_value"],
        alert["new_value"],
        alert["change_pct"],
        alert["priority"],
    ])


def write_ai_summary(summary: str) -> None:
    ws = _worksheet("AI_Summary")
    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), summary])
