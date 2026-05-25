#!/usr/bin/env python3
"""
AI Response Agent
- PRAW posts replies to Reddit leads
- Ollama generates personalized responses (free, local)
- Conservative rate limiting to protect account
- Only targets unresponded, high-quality Reddit leads
"""
import os, sys, time, json, sqlite3, requests, logging
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/var/log/response_agent.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

try:
    import praw
except ImportError:
    log.error("praw not installed: pip3 install praw --break-system-packages")
    sys.exit(1)

DB = '/var/www/contractor_app/instance/contractor_leads.db'
OLLAMA = 'http://localhost:11434/api/generate'
MODEL = 'llama3.2:3b'
MIN_SCORE = float(os.environ.get('MIN_SCORE_RESPOND', '6.5'))
DELAY_BETWEEN = int(os.environ.get('RESPONSE_DELAY_SEC', '180'))   # 3 min between posts
BATCH = int(os.environ.get('RESPONSE_BATCH', '5'))
CYCLE_SLEEP = int(os.environ.get('RESPONSE_CYCLE_MIN', '30')) * 60  # 30 min between cycles


def get_reddit():
    client_id = os.environ.get('REDDIT_CLIENT_ID')
    client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
    username = os.environ.get('REDDIT_USERNAME')
    password = os.environ.get('REDDIT_PASSWORD')
    if not all([client_id, client_secret, username, password]):
        log.error("Missing REDDIT_* env vars")
        sys.exit(1)
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent=f"ContractorLeadBot/1.0 by u/{username}"
    )


def ask_ollama(prompt):
    try:
        r = requests.post(OLLAMA, json={
            'model': MODEL, 'prompt': prompt, 'stream': False
        }, timeout=90)
        r.raise_for_status()
        return r.json().get('response', '').strip()
    except Exception as e:
        log.error(f"Ollama error: {e}")
        return None


def craft_response(lead):
    prompt = (
        f"A homeowner posted on Reddit asking for contractor help.\n"
        f"Title: {lead['title']}\n"
        f"Post: {str(lead['post_text'] or lead['description'] or '')[:400]}\n"
        f"Trade needed: {lead['keyword']}\n"
        f"Location: {lead['location']}\n\n"
        f"Write a single helpful Reddit comment (2-3 sentences, under 80 words) that:\n"
        f"- Acknowledges their specific need naturally\n"
        f"- Mentions you can connect them with vetted licensed contractors in their area\n"
        f"- Asks one qualifying question (when they need it, or scope of work)\n"
        f"- Sounds like a helpful neighbor, NOT a salesperson\n"
        f"Reply with only the comment text, nothing else."
    )
    return ask_ollama(prompt)


def get_pending_leads(conn, limit):
    rows = conn.execute("""
        SELECT id, source_url, title, description, post_text, keyword, location, quality_score
        FROM leads
        WHERE source IN ('reddit','brave_reddit')
          AND source_url LIKE '%reddit.com%'
          AND (response_status IS NULL OR response_status = 'pending')
          AND quality_score >= ?
          AND active = 1
        ORDER BY quality_score DESC, id DESC
        LIMIT ?
    """, (MIN_SCORE, limit)).fetchall()
    return [{'id': r[0], 'url': r[1], 'title': r[2], 'description': r[3],
             'post_text': r[4], 'keyword': r[5], 'location': r[6], 'score': r[7]}
            for r in rows]


def mark_responded(conn, lead_id, status='responded'):
    conn.execute("UPDATE leads SET response_status=? WHERE id=?", (status, lead_id))
    conn.commit()


def run_cycle(reddit, conn):
    leads = get_pending_leads(conn, BATCH)
    if not leads:
        log.info("No leads to respond to")
        return 0

    log.info(f"Processing {len(leads)} leads (min score {MIN_SCORE})")
    responded = 0

    for lead in leads:
        log.info(f"Lead #{lead['id']} score={lead['score']} | {lead['title'][:60]}")

        response_text = craft_response(lead)
        if not response_text:
            log.warning(f"Lead #{lead['id']}: Ollama returned nothing, skipping")
            mark_responded(conn, lead['id'], 'response_failed')
            continue

        log.info(f"Generated: {response_text[:100]}")

        try:
            submission = reddit.submission(url=lead['url'])
            submission.reply(response_text)
            mark_responded(conn, lead['id'], 'responded')
            log.info(f"Posted reply to {lead['url']}")
            responded += 1
        except praw.exceptions.RedditAPIException as e:
            code = e.items[0].error_type if e.items else str(e)
            log.error(f"Reddit API error: {code} — {e}")
            if 'RATELIMIT' in str(e).upper():
                log.warning("Rate limited — sleeping 10 min")
                time.sleep(600)
            elif 'DELETED' in str(e).upper() or 'NOT_FOUND' in str(e).upper():
                mark_responded(conn, lead['id'], 'post_deleted')
            else:
                mark_responded(conn, lead['id'], 'error')
        except Exception as e:
            log.error(f"Failed to post: {e}")
            mark_responded(conn, lead['id'], 'error')

        if responded < len(leads):
            log.info(f"Waiting {DELAY_BETWEEN}s before next post...")
            time.sleep(DELAY_BETWEEN)

    return responded


if __name__ == '__main__':
    log.info("Response Agent starting")
    log.info(f"Min score: {MIN_SCORE} | Delay: {DELAY_BETWEEN}s | Batch: {BATCH} | Cycle: {CYCLE_SLEEP//60}min")

    reddit = get_reddit()
    log.info(f"Reddit auth: u/{reddit.user.me().name}")

    conn = sqlite3.connect(DB)

    while True:
        try:
            n = run_cycle(reddit, conn)
            log.info(f"Cycle done: {n} responses posted")
        except Exception as e:
            log.error(f"Cycle error: {e}")
        log.info(f"Sleeping {CYCLE_SLEEP//60} min until next cycle")
        time.sleep(CYCLE_SLEEP)
