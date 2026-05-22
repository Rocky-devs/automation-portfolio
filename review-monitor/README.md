# AI-Powered Review Sentiment Monitor

Automated pipeline that monitors Google Maps reviews, analyzes sentiment with AI, and sends real-time alerts for negative feedback.

📧 contact: zl103795192@gmail.com

## Live Demo
[Watch demo video](https://youtu.be/kv1bD61ZQUA)

## Architecture

Python (Google Maps API) → Flask API (Railway) → Make.com Webhook
→ OpenRouter LLM (Sentiment Analysis) → Google Sheets (Storage)
→ Gmail Alert (Negative reviews only)

## Features
- Scrapes latest reviews via Google Maps Places API
- Deduplication using Google Sheets as persistent state (no repeated alerts)
- AI sentiment classification: POSITIVE / NEGATIVE / NEUTRAL
- Real-time Gmail alerts for negative reviews only
- Cloud-deployed Flask API on Railway, scheduled via Make.com

## Tech Stack
`Python` `Flask` `Make.com` `Google Maps API` `OpenRouter LLM` `Google Sheets API` `Railway`

## How It Works
1. Make.com triggers Flask API on schedule
2. Flask fetches latest reviews, compares timestamps with Sheets to deduplicate
3. New reviews are sent to Make.com webhook
4. Make runs AI sentiment analysis via OpenRouter
5. All reviews stored in Google Sheets with sentiment label
6. Negative reviews trigger immediate Gmail alert

