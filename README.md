# Automation Portfolio
Production-grade automation projects built with Python, Flask, n8n, and AI integration. Each project is deployed and live.

---

📧 zl103795192@gmail.com

## Projects

### [Dental Clinic AI Receptionist + Appointment Automation](./dental-clinic-ai-receptionist/)
Full AI receptionist and appointment automation system for dental clinics. Handles both online bookings and after-hours calls automatically.

**Stack**: Retell AI · n8n · Railway · Tally · Gmail · Telegram

**Highlights**:
- AI voice receptionist answers after-hours calls (Retell AI)
- Online booking via form with instant clinic notifications
- Patient confirmation email auto-sent
- Single workflow handles both form and voice inputs
- WhatsApp / SMS integration available

**Demo**: [Watch Video](https://youtu.be/2kE0Pue_Cjk)

---

### [Amazon Competitor Intelligence System](./amazon-competitor-intel/)
Automated Amazon competitor monitoring — tracks price, rating, reviews, and BSR across multiple ASINs. Delivers AI-prioritized daily alerts to Gmail. Runs 24/7 on Railway, triggered by self-hosted n8n.

**Stack**: Python · Flask · Rainforest API · Google Sheets · OpenRouter AI · n8n · Railway

**Highlights**:
- Detects price drops, rating changes, review spikes, BSR shifts
- AI-generated HIGH / MEDIUM / LOW priority summary per run
- Modular backend — easy to extend with new data sources or alert types

---

### [Google Maps Review Monitor](./review-monitor/)
Automated review monitoring for local businesses. Fetches new Google Maps reviews on a schedule, detects sentiment shifts, and sends alerts when negative reviews appear.

**Stack**: Python · Flask · Google Maps API · n8n · Railway

---

### [Reddit Lead Monitor](./reddit_monitor/)
Monitors 16 subreddits in real time for potential freelance leads. Two-stage filtering: keyword rules for fast pre-screening, then LLM batch analysis to qualify genuine business pain points. Matched posts are pushed to Telegram with silent-hour queuing (JST 10:00–23:00).

**Stack**: Python · OpenRouter AI · Llama 3.3 70B · Telegram Bot API · Railway

**Highlights**:
- 42 keyword rules across pain-point categories
- LLM batch filtering — up to 5 posts per API call
- Silent-hour queue — off-hours matches held and delivered at 10:00 JST
- Stateless design — safe to restart anytime

---

## Tech Stack Overview

| Layer | Tools |
|-------|-------|
| Backend | Python · Flask |
| Deployment | Railway |
| Automation | n8n (self-hosted) |
| AI Voice | Retell AI |
| Storage | Google Sheets · PostgreSQL |
| AI | OpenRouter · Llama 3.3 70B |
| Data sources | Rainforest API · Google Maps API · Reddit API |
| Notifications | Gmail · Telegram · WhatsApp |
| Dashboard | Looker Studio |

---

## About
Built by Rocky — freelance automation developer based in Japan.
Available for custom automation projects on [Upwork](https://www.upwork.com) and [Fiverr](https://www.fiverr.com).

📧 zl103795192@gmail.com
