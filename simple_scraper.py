#!/usr/bin/env python3
"""Simple Reddit scraper - no agent registration needed"""
import praw
import sys
sys.path.append('/var/www/contractor_app')
from app import app, db, Lead
from datetime import datetime

# Reddit (read-only, no auth needed)
reddit = praw.Reddit(
    client_id="",  # Empty for read-only
    client_secret="",
    user_agent="script:lead-scraper:v1.0"
)

KEYWORDS = ["electrician", "plumber", "contractor", "hvac", "landscaping", "pool service", "lawn maintenance", "maid service"]
LOCATIONS = ["Tampa FL", "Sarasota FL", "North Port FL"]

print(f"Scraping {len(KEYWORDS)} trades in {len(LOCATIONS)} locations...")

with app.app_context():
    total = 0
    for keyword in KEYWORDS:
        for location in LOCATIONS:
            query = f"{keyword} {location}"
            print(f"Searching: {query}")
            
            for submission in reddit.subreddit('all').search(query, limit=5):
                # Check if already exists
                if Lead.query.filter_by(source_url=submission.url).first():
                    continue
                
                lead = Lead(
                    source='reddit',
                    source_url=submission.url,
                    keyword=keyword,
                    title=submission.title,
                    description=submission.selftext[:500],
                    post_text=submission.selftext,
                    location=location,
                    posted_at=datetime.fromtimestamp(submission.created_utc),
                    scraped_at=datetime.utcnow(),
                    review_status='pending'
                )
                db.session.add(lead)
                total += 1
            
            db.session.commit()
    
    print(f"\n✅ Collected {total} new leads!")
    print(f"Total leads in database: {Lead.query.count()}")
