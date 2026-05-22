# Amazon Competitor Intelligence System — Phase 1

Automated Amazon competitor monitoring for sellers. Tracks price, rating, reviews, and BSR across multiple ASINs. Delivers AI-prioritized daily alerts straight to your inbox — no manual checking required. Runs 24/7 on Railway, triggered by self-hosted n8n.

📧 zl103795192@gmail.com
---

## Architecture

```
n8n (Schedule Trigger · daily)
    ↓ POST /run-monitor
Flask API (Railway)
    ├── Rainforest API  →  live product snapshot
    ├── Google Sheets   →  read ASIN list, write history + alerts
    └── OpenRouter AI   →  generate priority summary
    ↓ JSON response
n8n
    └── Gmail notification (if alerts > 0)
         ↓
Looker Studio ← Google Sheets (dashboard)
```

---

## Alert types

| Type | Trigger | Priority |
|------|---------|----------|
| PRICE_DROP | Price fell ≥ threshold % | HIGH |
| PRICE_INCREASE | Price rose ≥ threshold % | MEDIUM |
| RATING_DROP | Rating fell ≥ 0.1 stars | HIGH |
| RATING_RISE | Rating rose ≥ 0.1 stars | LOW |
| REVIEW_SPIKE | +10 reviews or +2% | MEDIUM |
| REVIEW_DROP | Reviews decreased | MEDIUM |
| BSR_IMPROVE | BSR rank # fell ≥ 20% | HIGH |
| BSR_DECLINE | BSR rank # rose ≥ 20% | MEDIUM |

---

## Tech stack

| Layer | Tool |
|-------|------|
| Data source | Rainforest API (Amazon product data) |
| Backend | Python · Flask · Railway |
| Storage | Google Sheets (gspread) |
| Automation | n8n self-hosted (PostgreSQL backend) |
| AI summary | OpenRouter · Llama 3.3 70B (free tier) |
| Notification | Gmail via n8n |
| Dashboard | Looker Studio |

---

## Project structure

```
amazon-competitor-intel/
├── app.py           # Flask API + route handlers
├── rainforest.py    # Rainforest API wrapper
├── sheets.py        # Google Sheets read/write
├── analyzer.py      # Change detection + alert generation
├── ai_summary.py    # OpenRouter AI daily summary
├── requirements.txt
├── railway.toml     # Railway deploy config
└── Procfile
```

---

## Google Sheets setup

Create one spreadsheet with 4 tabs (headers must match exactly):

**ASIN_List**
| ASIN | Product_Name | Alert_Threshold_Pct | Active |
|------|-------------|---------------------|--------|
| B073JYC4XM | SanDisk 128GB | 5 | Y |

- `Alert_Threshold_Pct`: minimum % price change to trigger alert (default 5)
- `Active`: Y = monitor, N = skip

**Product_History**
| Timestamp | ASIN | Title | Price | Rating | Reviews_Count | BSR |

**Alerts_Log**
| Timestamp | ASIN | Alert_Type | Old_Value | New_Value | Change_Pct | Priority |

**AI_Summary**
| Timestamp | Summary |

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `RAINFOREST_API_KEY` | From rainforestapi.com |
| `GOOGLE_CREDENTIALS_JSON` | Service account JSON (minified, one line) — used on Railway |
| `GOOGLE_CREDENTIALS_PATH` | Local dev only — path to service account JSON file |
| `SPREADSHEET_ID` | Google Sheet ID from the URL |
| `OPENROUTER_API_KEY` | From openrouter.ai |
| `WEBHOOK_SECRET` | Random string for endpoint auth (`openssl rand -hex 16`) |

### Getting GOOGLE_CREDENTIALS_JSON

1. Google Cloud Console → create or select a project
2. Enable **Google Sheets API**
3. IAM → Service Accounts → Create → download JSON key
4. Share your Google Sheet with the service account email (Editor access)
5. Minify the JSON to one line:
```bash
cat key.json | tr -d '\n' | pbcopy
```
6. Paste as the `GOOGLE_CREDENTIALS_JSON` variable value in Railway

---

## Local development

```bash
git clone https://github.com/Rocky-devs/automation-portfolio
cd automation-portfolio/amazon-competitor-intel
pip install -r requirements.txt
pip install python-dotenv
```

Create `.env`:
```
RAINFOREST_API_KEY=your_key
GOOGLE_CREDENTIALS_PATH=/path/to/service-account.json
SPREADSHEET_ID=your_spreadsheet_id
OPENROUTER_API_KEY=your_key
WEBHOOK_SECRET=your_secret
PORT=5001
```

Run and test:
```bash
python app.py

# Health check
curl http://localhost:5001/health

# Single ASIN fetch
curl http://localhost:5001/snapshot/B073JYC4XM \
  -H "X-Secret-Key: YOUR_SECRET"

# Full monitor run
curl -X POST http://localhost:5001/run-monitor \
  -H "X-Secret-Key: YOUR_SECRET"
```

---

## Railway deployment

```bash
railway login
railway init
railway up

railway variables set RAINFOREST_API_KEY=xxx
railway variables set GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'
railway variables set SPREADSHEET_ID=xxx
railway variables set OPENROUTER_API_KEY=xxx
railway variables set WEBHOOK_SECRET=xxx
```

---

## n8n workflow

Self-hosted n8n (Railway + PostgreSQL) triggers the monitoring cycle:

```
Schedule Trigger (daily 9am)
    → HTTP Request POST /run-monitor
       Header: X-Secret-Key
    → IF alerts_count > 0
        → Gmail: send formatted HTML alert email
```

---

## API reference

### `GET /health`
No auth required.
```json
{"status": "ok", "timestamp": "2026-05-19T09:00:00"}
```

### `POST /run-monitor`
Header: `X-Secret-Key: YOUR_SECRET`

```json
{
  "status": "success",
  "run_at": "2026-05-19T09:00:41",
  "asins_processed": 3,
  "alerts_count": 1,
  "alerts": [
    {
      "asin": "B073JYC4XM",
      "type": "PRICE_DROP",
      "old_value": 49.99,
      "new_value": 32.95,
      "change_pct": -34.1,
      "priority": "HIGH",
      "timestamp": "2026-05-19 09:00"
    }
  ],
  "ai_summary": "🔴 HIGH: Competitor dropped price 34%...\n💡 ACTION: Review pricing strategy.",
  "errors": []
}
```

### `GET /snapshot/<asin>`
Header: `X-Secret-Key: YOUR_SECRET`

Manual single-ASIN fetch for testing. Returns raw product data without writing to Sheets.

---

## API usage tracking

Free tier: 100 requests/month.

| Setup | Calls/month | |
|-------|-------------|---|
| 10 ASINs · every 3 days | ~100 | ✅ |
| 5 ASINs · every 2 days | ~75 | ✅ |
| 3 ASINs · daily | ~90 | ✅ |
| 10 ASINs · daily | ~310 | ❌ |

---

## Looker Studio setup

1. Connect data source: Google Sheets → your spreadsheet
2. Suggested charts:
   - **Price history**: line chart, X = Timestamp, Y = Price, dimension = ASIN (Product_History tab)
   - **BSR trend**: line chart from Product_History
   - **Alerts table**: table from Alerts_Log, filter by Priority
   - **Rating tracker**: line chart from Product_History

---

## Phase 2 roadmap

- Buy Box winner monitoring
- Inventory / stockout detection
- Promotional event identification
- Negative review content classification
- Auto pricing suggestions
- Weekly PDF report generation
- Multi-marketplace support (amazon.co.uk, amazon.co.jp)

---

## Portfolio notes

**Upwork pitch**: "I built a production competitor intel system using Rainforest API + Google Sheets + n8n + AI summaries. Deployed on Railway with webhook security, runs 24/7 without any manual intervention. Can replicate or extend this for your Amazon store within a week."

**Demo flow**: ASIN_List tab → trigger n8n Execute workflow → Product_History shows new row → Gmail alert arrives → Looker Studio dashboard
