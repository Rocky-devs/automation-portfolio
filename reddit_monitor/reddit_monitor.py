"""
Reddit Keyword Monitor
监控目标subreddit的潜在客户帖子 → LLM二次过滤 → Telegram推送

流程：
  关键词匹配（粗筛）→ OpenRouter LLM判断是否真实lead（精筛）→ 推送
  JST 10:00-23:00 实时推送，静默期入队，10:00开启时批量推积压
"""

import requests
import json
import time
import os
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
OPENROUTER_KEY   = os.getenv("OPENROUTER_KEY",   "")

# 用哪个模型：便宜快 → meta-llama/llama-3.1-8b-instruct:free 或 mistralai/mistral-7b-instruct:free
LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

SUBREDDITS = [
    # 原有
    "smallbusiness",
    "ecommerce",
    "Entrepreneur",
    # 新增 - 创业者
    "startups",
    "SaaS",
    "sideproject",
    # 新增 - 电商
    "AmazonSeller",
    "FulfillmentByAmazon",
    "shopify",
    "EtsySellers",
    # 新增 - 营销运营
    "marketing",
    "digital_marketing",
    # 新增 - 自动化意识强
    "Excel",
    "Notion",
    "zapier",
    "n8n",
]

KEYWORD_RULES = [
    # 原有
    ["takes me hours"],
    ["hours every week"],
    ["hours a week"],
    ["spend hours"],
    ["manually", "spreadsheet"],
    ["manually", "excel"],
    ["manually", "report"],
    ["manually", "data"],
    ["manually", "update"],
    ["manually", "entering"],
    ["waste time", "excel"],
    ["waste time", "spreadsheet"],
    ["waste time", "data"],
    ["automate", "spreadsheet"],
    ["automate", "excel"],
    ["scrape", "website"],
    ["web scraping"],
    # 新增 - 时间成本
    ["taking forever"],
    ["so much time"],
    ["can't keep up"],
    ["overwhelmed", "data"],
    ["too much time", "manual"],
    # 新增 - 痛苦表达
    ["tired of", "manually"],
    ["tired of", "spreadsheet"],
    ["frustrating", "data"],
    ["annoying", "manually"],
    ["copy paste", "every"],
    ["copy and paste"],
    ["manually download"],
    ["manually check"],
    ["manually track"],
    # 新增 - 求工具/方案
    ["any tool", "automate"],
    ["is there a way", "automate"],
    ["need help", "automate"],
    ["looking for", "automation"],
    ["solution for", "spreadsheet"],
    # 新增 - 爬虫需求
    ["scrape", "data"],
    ["extract", "website"],
    ["pull data", "website"],
    ["price monitoring"],
    ["monitor", "competitor"],
    ["competitor", "price"],
]

POLL_INTERVAL_SEC = 60 * 60
DEFAULT_LOOKBACK  = 12 * 60 * 60
PUSH_HOUR_START   = 10
PUSH_HOUR_END     = 23
JST               = timezone(timedelta(hours=9))

DEPLOYMENT = os.getenv("DEPLOYMENT", "local")
STATE_FILE = Path("last_run_time.txt")
QUEUE_FILE = Path("pending_queue.json")

HEADERS = {"User-Agent": "RedditMonitor/1.0 (personal tool)"}

# ============================================================
# 时间判断
# ============================================================

def is_push_time() -> bool:
    return PUSH_HOUR_START <= datetime.now(JST).hour <= PUSH_HOUR_END

def jst_now_str() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

# ============================================================
# last_run_time
# ============================================================

def load_last_run_time() -> float:
    max_lookback = time.time() - DEFAULT_LOOKBACK  # 最多往回看12小时

    if DEPLOYMENT == "local" and STATE_FILE.exists():
        try:
            val = float(STATE_FILE.read_text().strip())
            # 如果上次运行时间超过12小时前，就只从12小时前开始
            result = max(val, max_lookback)
            log.info(f"上次运行: {datetime.fromtimestamp(val, tz=JST).strftime('%m-%d %H:%M JST')}")
            if result != val:
                log.info(f"上次运行超过{DEFAULT_LOOKBACK//3600}小时前，截断到{DEFAULT_LOOKBACK//3600}小时前")
            return result
        except Exception:
            pass

    log.info(f"首次运行，从{DEFAULT_LOOKBACK//3600}小时前开始")
    return max_lookback

def save_last_run_time(ts: float):
    if DEPLOYMENT == "local":
        STATE_FILE.write_text(str(ts))

# ============================================================
# 队列管理
# ============================================================

def load_queue() -> list:
    if DEPLOYMENT == "railway":
        return []
    if QUEUE_FILE.exists():
        try:
            return json.loads(QUEUE_FILE.read_text())
        except Exception:
            return []
    return []

def save_queue(queue: list):
    if DEPLOYMENT == "local":
        QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2))

def add_to_queue(queue: list, post: dict, matched_rule: str, llm_reason: str) -> list:
    existing_ids = {item["id"] for item in queue}
    if post["id"] not in existing_ids:
        queue.append({
            "id":           post["id"],
            "title":        post.get("title", ""),
            "subreddit":    post.get("subreddit", ""),
            "author":       post.get("author", ""),
            "score":        post.get("score", 0),
            "permalink":    post.get("permalink", ""),
            "body_preview": post.get("selftext", "")[:200].strip(),
            "created_utc":  post.get("created_utc", 0),
            "matched_rule": matched_rule,
            "llm_reason":   llm_reason,
        })
    return queue

# ============================================================
# 关键词匹配（粗筛）
# ============================================================

def matches_any_rule(title: str, body: str) -> tuple[bool, str]:
    text = (title + " " + body).lower()
    for rule in KEYWORD_RULES:
        if all(kw.lower() in text for kw in rule):
            return True, " + ".join(rule)
    return False, ""

# ============================================================
# LLM批量过滤（精筛）
# 每次最多5条帖子合并一次API调用，大幅减少请求数
# ============================================================

BATCH_SIZE = 5  # 每批处理帖子数

SYSTEM_PROMPT = """You are a lead-qualification assistant for a freelancer who offers:
- Web scraping & data extraction (Python, Playwright, Scrapy)
- Data cleaning & analysis (pandas, Excel automation)
- Workflow automation (n8n, Make, Zapier, Python scripts)

You will receive multiple Reddit posts. For EACH post, decide if it's a REAL potential paying lead.

APPROVE (is_lead: true) if the post author:
- Has a specific business pain point involving manual data work or repetitive tasks
- Implies they want someone to solve it for them (asking for tools, services, or help)
- Is a business owner, operator, or someone with budget authority

REJECT (is_lead: false) if the post is:
- Pure technical discussion or tutorial (how do I learn X)
- Someone sharing their own solution or experience
- General news, opinions, or venting without a specific ask
- A developer asking how to build something themselves
- Promotional content

Respond ONLY with a valid JSON array, one object per post, in the same order:
[
  {"id": "post_id", "is_lead": true, "reason": "one sentence"},
  {"id": "post_id", "is_lead": false, "reason": "one sentence"}
]
No extra text, no markdown."""


def llm_filter_batch(candidates: list[dict]) -> list[dict]:
    """
    批量调用LLM过滤，每批最多BATCH_SIZE条
    candidates: [{"id", "title", "body", "subreddit"}, ...]
    返回: [{"id", "is_lead", "reason"}, ...]
    失败时全部默认放行
    """
    if not candidates:
        return []

    if not OPENROUTER_KEY:
        log.warning("未配置OPENROUTER_KEY，跳过LLM过滤")
        return [{"id": c["id"], "is_lead": True, "reason": "LLM未配置"} for c in candidates]

    # 构造用户消息：每条帖子编号
    posts_text = ""
    for c in candidates:
        body_preview = c["body"][:300] if c["body"] else "(no body)"
        posts_text += (
            f"---\n"
            f"ID: {c['id']}\n"
            f"Subreddit: r/{c['subreddit']}\n"
            f"Title: {c['title']}\n"
            f"Body: {body_preview}\n"
        )

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": posts_text},
                ],
                "max_tokens": 300,
                "temperature": 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)

        # 确保返回list
        if isinstance(results, dict):
            results = [results]
        return results

    except json.JSONDecodeError:
        log.warning(f"LLM返回非JSON，全部放行: {raw[:150]}")
    except Exception as e:
        log.warning(f"LLM批量调用失败，全部放行: {e}")

    # 失败默认放行
    return [{"id": c["id"], "is_lead": True, "reason": f"LLM错误，放行"} for c in candidates]


def llm_filter_posts(hits: list[dict]) -> list[tuple[dict, str]]:
    """
    对关键词命中的帖子做批量LLM过滤
    hits: [{"post": reddit_post_dict, "rule": matched_rule}, ...]
    返回通过过滤的 [(post, rule, reason), ...]
    """
    if not hits:
        return []

    # 分批处理
    passed = []
    for i in range(0, len(hits), BATCH_SIZE):
        batch = hits[i:i + BATCH_SIZE]
        candidates = [
            {
                "id":       h["post"]["id"],
                "title":    h["post"].get("title", ""),
                "body":     h["post"].get("selftext", ""),
                "subreddit": h["post"].get("subreddit", ""),
            }
            for h in batch
        ]

        results = llm_filter_batch(candidates)

        # 建立 id → result 映射
        result_map = {r["id"]: r for r in results}

        for h in batch:
            pid    = h["post"]["id"]
            result = result_map.get(pid, {"is_lead": True, "reason": "未找到结果，放行"})
            if result.get("is_lead", True):
                passed.append((h["post"], h["rule"], result.get("reason", "")))
            else:
                log.info(f"❌ LLM过滤: [{h['post'].get('subreddit','')}] {h['post'].get('title','')[:50]} | {result.get('reason','')}")

        # 批次间稍作等待，避免连续请求
        if i + BATCH_SIZE < len(hits):
            time.sleep(2)

    return passed

# ============================================================
# Reddit API
# ============================================================

def fetch_new_posts(subreddit: str) -> list:
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=25&sort=new"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return [item["data"] for item in resp.json()["data"]["children"]]
    except Exception as e:
        log.warning(f"拉取 r/{subreddit} 失败: {e}")
        return []

# ============================================================
# Telegram
# ============================================================

def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Telegram推送失败: {e}")
        return False

def _build_message(title, subreddit, author, score, permalink,
                   body_preview, created_utc, matched_rule, llm_reason, tag=""):
    created = datetime.fromtimestamp(created_utc, tz=JST).strftime("%m-%d %H:%M JST")
    preview = f"\n📄 <i>{body_preview}...</i>" if body_preview else ""
    tag_str = f"{tag} " if tag else ""
    return (
        f"🎯 {tag_str}<b>潜在客户帖子</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{title}</b>\n"
        f"🔑 关键词: <code>{matched_rule}</code>\n"
        f"🤖 LLM: <i>{llm_reason}</i>\n"
        f"👤 u/{author} | r/{subreddit} | ⬆️ {score}"
        f"{preview}\n"
        f"🕐 {created}\n"
        f"🔗 <a href='https://reddit.com{permalink}'>查看原帖</a>"
    )

def format_message_from_post(post: dict, matched_rule: str, llm_reason: str) -> str:
    return _build_message(
        title        = post.get("title", ""),
        subreddit    = post.get("subreddit", ""),
        author       = post.get("author", ""),
        score        = post.get("score", 0),
        permalink    = post.get("permalink", ""),
        body_preview = post.get("selftext", "")[:200].strip(),
        created_utc  = post.get("created_utc", 0),
        matched_rule = matched_rule,
        llm_reason   = llm_reason,
    )

def format_message_from_queue(item: dict) -> str:
    return _build_message(
        title        = item["title"],
        subreddit    = item["subreddit"],
        author       = item["author"],
        score        = item["score"],
        permalink    = item["permalink"],
        body_preview = item["body_preview"],
        created_utc  = item["created_utc"],
        matched_rule = item["matched_rule"],
        llm_reason   = item.get("llm_reason", ""),
        tag          = "[积压]",
    )

# ============================================================
# 推送积压队列
# ============================================================

def flush_queue(queue: list) -> list:
    if not queue:
        return []
    log.info(f"推送积压队列：{len(queue)} 条")
    send_telegram(f"📬 <b>推送昨晚积压帖子（共{len(queue)}条）</b>")
    time.sleep(1)
    remaining = []
    for item in queue:
        if send_telegram(format_message_from_queue(item)):
            log.info(f"✅ 积压推送: {item['title'][:60]}")
            time.sleep(1)
        else:
            remaining.append(item)
    return remaining

# ============================================================
# 主扫描
# ============================================================

def run_once(last_run_time: float, queue: list) -> tuple[int, int, list]:
    """
    扫描一轮
    返回 (推送数, LLM过滤数, 更新后队列)
    """
    push_mode = is_push_time()
    pushed    = 0
    filtered  = 0
    hits      = []  # 关键词命中的帖子，等待批量LLM过滤

    # 第一层：关键词粗筛（全部subreddit）
    for subreddit in SUBREDDITS:
        posts     = fetch_new_posts(subreddit)
        new_posts = [p for p in posts if p.get("created_utc", 0) > last_run_time]
        if new_posts:
            log.info(f"r/{subreddit}: {len(new_posts)}条新帖")

        for post in new_posts:
            hit, rule = matches_any_rule(
                post.get("title", ""),
                post.get("selftext", "")
            )
            if hit:
                hits.append({"post": post, "rule": rule})

        time.sleep(2)  # 避免Reddit限速

    log.info(f"关键词命中: {len(hits)}条 → 送入LLM批量过滤")

    # 第二层：LLM批量精筛
    if hits:
        passed = llm_filter_posts(hits)
        filtered = len(hits) - len(passed)

        for post, rule, reason in passed:
            if push_mode:
                msg = format_message_from_post(post, rule, reason)
                if send_telegram(msg):
                    pushed += 1
                    log.info(f"✅ 推送: [{post.get('subreddit','')}] {post.get('title','')[:60]}")
                    time.sleep(1)
            else:
                queue = add_to_queue(queue, post, rule, reason)
                log.info(f"🔕 入队: [{post.get('subreddit','')}] {post.get('title','')[:60]}")

    return pushed, filtered, queue

# ============================================================
# 主循环
# ============================================================

def main():
    log.info(f"Reddit Monitor 启动 | 模式: {DEPLOYMENT} | 轮询: {POLL_INTERVAL_SEC//60}分钟")
    log.info(f"推送时段: JST {PUSH_HOUR_START}:00-{PUSH_HOUR_END}:59 | LLM: {LLM_MODEL}")
    log.info(f"监控 {len(SUBREDDITS)} 个 subreddit | {len(KEYWORD_RULES)} 条关键词规则")

    last_run_time = load_last_run_time()
    queue         = load_queue()

    send_telegram(
        f"🚀 <b>Reddit Monitor 启动</b>\n"
        f"监控: {len(SUBREDDITS)}个subreddit | {len(KEYWORD_RULES)}条规则\n"
        f"推送时段: {PUSH_HOUR_START}:00-{PUSH_HOUR_END}:59 JST\n"
        f"积压队列: {len(queue)}条 | 模式: {DEPLOYMENT}\n"
        f"LLM过滤: {LLM_MODEL.split('/')[-1]}"
    )

    prev_push = is_push_time()

    while True:
        run_start   = time.time()
        in_push_now = is_push_time()

        log.info(f"--- 扫描 {jst_now_str()} {'[推送]' if in_push_now else '[静默]'} 队列:{len(queue)}条 ---")

        # 推送窗口刚开启 → 先推积压
        if in_push_now and not prev_push and queue:
            queue = flush_queue(queue)
            save_queue(queue)

        pushed, filtered, queue = run_once(last_run_time, queue)
        save_queue(queue)

        last_run_time = run_start
        prev_push     = in_push_now
        save_last_run_time(last_run_time)

        log.info(f"本轮: 推送{pushed}条 | LLM过滤{filtered}条 | 积压{len(queue)}条 | {POLL_INTERVAL_SEC//60}分钟后再扫")
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
