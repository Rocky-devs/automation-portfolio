# Reddit Lead Monitor

📧 zl103795192@gmail.com

Monitors Reddit in real time for freelance leads — businesses expressing pain points around manual data work, spreadsheets, scraping, or automation.

## How it works

New posts (every 60 min)
↓ keyword pre-filter (42 rules)
Matched posts
↓ LLM batch analysis (Llama 3.3 70B)
Qualified leads
↓ Telegram push (JST 10:00–23:00)

## Features

- Monitors 16 subreddits: r/smallbusiness, r/ecommerce, r/Entrepreneur, r/SaaS, r/shopify, r/AmazonSeller and more
- Two-stage filtering keeps LLM API usage minimal
- Silent-hour queuing — matches outside push window held and delivered at 10:00 JST
- 12-hour lookback cap on cold start — no stale leads after restart

## Stack

- Python (requests, logging)
- OpenRouter API — Llama 3.3 70B free tier
- Telegram Bot API
- Railway (deployment)

## Environment variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `OPENROUTER_KEY` | OpenRouter API key |
| `DEPLOYMENT` | Set to `railway` on cloud |

## Configuration

All tunable parameters at the top of `reddit_monitor.py`:

- `SUBREDDITS` — list of subreddits to monitor
- `KEYWORD_RULES` — keyword matching rules
- `POLL_INTERVAL_SEC` — polling interval (default 60 min)
- `DEFAULT_LOOKBACK` — max lookback on cold start (default 12 hours)
- `PUSH_HOUR_START / END` — push window in JST