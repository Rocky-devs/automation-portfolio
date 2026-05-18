# Amazon Competitor Intelligence System — Phase 1

Automated price, rating, review, and BSR monitoring for Amazon sellers.
Triggered by Make.com schedule → Flask API (Railway) → Google Sheets storage → AI daily summary → Gmail/Slack alerts.

---

## Architecture

```
Make.com (schedule)
    ↓ POST /run-monitor
Flask API (Railway)
    ├── Rainforest API  →  product snapshots
    ├── Google Sheets   →  read ASIN list, write history + alerts
    └── OpenRouter      →  AI daily summary
    ↓ JSON response
Make.com
    ├── Gmail notification
    └── Slack notification
         ↓
Looker Studio ← Google Sheets (visualization)
```

---

## Google Sheets Setup

Create one spreadsheet and add **4 tabs** with these exact headers (Row 1):

### ASIN_List
| ASIN | Product_Name | Alert_Threshold_Pct | Active |
|------|-------------|---------------------|--------|
| B08N5WRWNW | Echo Dot 5th Gen | 5 | Y |

- `Alert_Threshold_Pct`: minimum % price change to trigger alert (default 5)
- `Active`: Y = monitor, N = skip

### Product_History
| Timestamp | ASIN | Title | Price | Rating | Reviews_Count | BSR |
|-----------|------|-------|-------|--------|---------------|-----|

### Alerts_Log
| Timestamp | ASIN | Alert_Type | Old_Value | New_Value | Change_Pct | Priority |
|-----------|------|-----------|-----------|-----------|------------|----------|

### AI_Summary
| Timestamp | Summary |
|-----------|---------|

---

## Environment Variables

Set these in Railway (or `.env` for local):

| Variable | Value |
|----------|-------|
| `RAINFOREST_API_KEY` | From rainforestapi.com |
| `GOOGLE_CREDENTIALS_JSON` | Service account JSON (minified, one line) |
| `SPREADSHEET_ID` | Google Sheet ID from URL |
| `OPENROUTER_API_KEY` | From openrouter.ai |
| `WEBHOOK_SECRET` | Any random string (e.g. `openssl rand -hex 16`) |

### Getting GOOGLE_CREDENTIALS_JSON

1. Google Cloud Console → Create project
2. Enable **Google Sheets API**
3. IAM → Service Accounts → Create → Download JSON key
4. Share your Google Sheet with the service account email (Editor access)
5. Minify the JSON to one line: `python3 -c "import json,sys; print(json.dumps(json.load(open('key.json'))))"` 
6. Paste as the env var value

---

## Local Development

```bash
git clone https://github.com/Rocky-devs/amazon-intel
cd amazon-intel
pip install -r requirements.txt

# Create .env file with all variables listed above
export $(cat .env | xargs)

python app.py
```

Test manually:
```bash
# Health check
curl http://localhost:5000/health

# Test single ASIN fetch
curl -H "X-Secret-Key: YOUR_SECRET" http://localhost:5000/snapshot/B08N5WRWNW

# Trigger full monitor run
curl -X POST -H "X-Secret-Key: YOUR_SECRET" http://localhost:5000/run-monitor
```

---

## Railway Deployment

```bash
# Install Railway CLI
npm install -g @railway/cli

railway login
railway init
railway up

# Set env vars
railway variables set RAINFOREST_API_KEY=xxx
railway variables set GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'
railway variables set SPREADSHEET_ID=xxx
railway variables set OPENROUTER_API_KEY=xxx
railway variables set WEBHOOK_SECRET=xxx
```

Note: Railway Hobby plan = $5/month. For portfolio demo, this is the most reliable option.
Alternative: Render free tier works but has ~30s cold start (May cause Make.com timeout — set webhook timeout to 60s).

---

## Make.com Workflow

### Module 1: Schedule
- Every 3 days (to stay within 100 API calls/month free tier)
- Or manually trigger for demo

### Module 2: HTTP → Make a Request
- URL: `https://YOUR-APP.railway.app/run-monitor`
- Method: POST
- Headers: `X-Secret-Key: YOUR_SECRET`
- Timeout: 60 seconds

### Module 3: Router (branch on alerts)
- Condition: `{{2.alerts_count}} > 0`

### Branch A: Gmail
- To: seller@email.com
- Subject: `[Intel Alert] {{2.alerts_count}} competitor changes detected`
- Body: Use `{{2.ai_summary}}` + format `{{2.alerts}}` array

### Branch B: Slack
- Channel: #competitor-intel
- Message: `{{2.ai_summary}}`

---

## API Reference

### `GET /health`
Returns `{"status": "ok", "timestamp": "..."}`. No auth required.

### `POST /run-monitor`
Header: `X-Secret-Key: YOUR_SECRET`

Response:
```json
{
  "status": "success",
  "run_at": "2026-05-14T09:00:00",
  "asins_processed": 5,
  "alerts_count": 2,
  "alerts": [
    {
      "timestamp": "2026-05-14 09:00",
      "asin": "B08N5WRWNW",
      "type": "PRICE_DROP",
      "old_value": 49.99,
      "new_value": 39.99,
      "change_pct": -20.0,
      "priority": "HIGH"
    }
  ],
  "ai_summary": "🔴 HIGH: Competitor dropped price 20%...\n💡 ACTION: Consider matching price or highlighting value.",
  "errors": []
}
```

### `GET /snapshot/<asin>`
Header: `X-Secret-Key: YOUR_SECRET`
Manual single-ASIN test endpoint.

---

## Alert Types

| Type | Trigger | Default Priority |
|------|---------|-----------------|
| PRICE_DROP | Price fell ≥ threshold % | HIGH |
| PRICE_INCREASE | Price rose ≥ threshold % | MEDIUM |
| RATING_DROP | Rating fell ≥ 0.1 stars | HIGH |
| RATING_RISE | Rating rose ≥ 0.1 stars | LOW |
| REVIEW_SPIKE | +10 reviews or +2% | MEDIUM |
| REVIEW_DROP | Reviews decreased | MEDIUM |
| BSR_IMPROVE | BSR rank # fell ≥ 20% | HIGH |
| BSR_DECLINE | BSR rank # rose ≥ 20% | MEDIUM |

---

## Looker Studio Setup

1. Connect data source: Google Sheets → your spreadsheet
2. Suggested charts:
   - **Price History**: Line chart, X=Timestamp, Y=Price, dimension=ASIN (from Product_History)
   - **BSR Trend**: Line chart from Product_History
   - **Alerts Table**: Table from Alerts_Log, filtered by Priority
   - **Rating Tracker**: Line chart from Product_History

---

## API Usage Tracking

Free tier: 100 requests/month.

| Setup | Calls/month |
|-------|-------------|
| 10 ASINs × every 3 days | ~100 ✅ |
| 5 ASINs × every 2 days | ~75 ✅ |
| 10 ASINs × daily | ~310 ❌ |

---

## Project Structure

```
amazon-intel/
├── app.py          # Flask API + route handlers
├── rainforest.py   # Rainforest API wrapper
├── sheets.py       # Google Sheets read/write
├── analyzer.py     # Change detection + alert generation
├── ai_summary.py   # OpenRouter LLM daily summary
├── requirements.txt
├── railway.toml    # Railway deploy config
├── Procfile        # Gunicorn start command
└── README.md
```

---

## Portfolio Notes

- **GitHub**: Push to `github.com/Rocky-devs/amazon-intel`
- **Loom demo flow**: Show Sheets → trigger Make.com → Railway logs → new rows appear in Sheets → Gmail notification → Looker Studio dashboard
- **Upwork pitch**: "I built a production competitor intel system using Rainforest API + Google Sheets + Make.com + AI summaries. Deployed on Railway with webhook security. Can replicate/extend for your Amazon store."
