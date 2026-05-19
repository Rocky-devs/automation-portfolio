"""
Generates a daily priority summary using OpenRouter (free llama model).
"""
import os
import re
import time
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.1-8b-instruct"


def _build_prompt(alerts: list[dict], products: list[dict]) -> str:
    product_lines = "\n".join(
        f"- {p['asin']} | ${p.get('price', 'N/A')} | ★{p.get('rating', 'N/A')} | BSR #{p.get('bsr', 'N/A')}"
        for p in products
    )

    if alerts:
        HIGH = [a for a in alerts if a["priority"] == "HIGH"]
        MED = [a for a in alerts if a["priority"] == "MEDIUM"]
        LOW = [a for a in alerts if a["priority"] == "LOW"]

        def fmt(a):
            return f"  [{a['priority']}] {a['asin']} | {a['type']}: {a['old_value']} → {a['new_value']} ({a['change_pct']:+})"

        alert_block = ""
        if HIGH:
            alert_block += "HIGH PRIORITY:\n" + "\n".join(fmt(a) for a in HIGH) + "\n"
        if MED:
            alert_block += "MEDIUM PRIORITY:\n" + "\n".join(fmt(a) for a in MED) + "\n"
        if LOW:
            alert_block += "LOW PRIORITY:\n" + "\n".join(fmt(a) for a in LOW)
    else:
        alert_block = "No significant changes detected."

    return f"""You are a concise Amazon competitive intelligence analyst writing a daily briefing for a seller.

PRODUCTS MONITORED TODAY:
{product_lines}

ALERTS:
{alert_block}

Write a daily summary in exactly this format:

🔴 HIGH: [1 sentence on most urgent item, or "None"]

🟡 MEDIUM: [1 sentence on medium items, or "None"]

🟢 LOW: [1 sentence on low items, or "None"]

💡 ACTION: [1 concrete action the seller should consider today]

Be direct. No fluff. Max 4 sentences total."""


def generate_summary(alerts: list[dict], products: list[dict]) -> str:
    prompt = _build_prompt(alerts, products)

    for attempt in range(3):
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Rocky-devs/amazon-intel",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3,
            },
            timeout=30,
        )

        if resp.status_code == 429:
            wait = 2 ** attempt * 10  # 10s, 20s, 40s
            print(f"[WARN] 429 限流，{wait}秒后重试 (attempt {attempt + 1}/3)")
            time.sleep(wait)
            continue

        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        content = re.sub(r'([🟡🟢💡])', r'\n\n\1', content)
        return content

    return "AI summary unavailable: rate limited after 3 retries."
