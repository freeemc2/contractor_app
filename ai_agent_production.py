#!/usr/bin/env python3
"""
AI Response Agent - Production Version
Only responds to APPROVED leads with human validation
"""
import sys
import praw
import requests
import json
from datetime import datetime
from reddit_config import REDDIT_CONFIG

# Database
sys.path.append('/var/www/contractor_app')
from app import db, Lead, app

def get_ollama_response(prompt):
    """Get AI response from local Ollama"""
    try:
        response = requests.post('http://localhost:11434/api/generate', json={
            'model': 'llama3.2:3b',
            'prompt': prompt,
            'stream': False
        })
        return response.json()['response']
    except Exception as e:
        print(f"Ollama error: {e}")
        return None

def craft_contractor_response(lead):
    """Generate personalized contractor response"""
    prompt = f"""You are a professional contractor responding to a potential customer on Reddit.

Customer's post:
Title: {lead.title}
Description: {lead.description}
Location: {lead.location}
Trade needed: {lead.keyword}

Write a helpful, professional response that:
1. Acknowledges their specific need
2. Mentions you're a licensed {lead.keyword} in {lead.location} area
3. Offers to help
4. Keeps it brief (3-4 sentences)
5. Sounds natural, not salesy

Response:"""
    
    return get_ollama_response(prompt)

def post_to_reddit(lead, response_text, dry_run=True):
    """Post response to Reddit"""
    if dry_run:
        print(f"\n[DRY RUN] Would post to: {lead.source_url}")
        print(f"Response: {response_text}\n")
        return True
    
    try:
        reddit = praw.Reddit(**REDDIT_CONFIG)
        submission = reddit.submission(url=lead.source_url)
        comment = submission.reply(response_text)
        print(f"✅ Posted: {comment.permalink}")
        return True
    except Exception as e:
        print(f"❌ Reddit error: {e}")
        return False

def process_approved_leads(dry_run=True, limit=5):
    """Process approved leads only"""
    with app.app_context():
        # Get approved leads that haven't been responded to
        leads = Lead.query.filter_by(
            review_status='approved',
            ai_processed=False
        ).limit(limit).all()
        
        print(f"\n📊 Found {len(leads)} approved leads to process")
        
        for lead in leads:
            print(f"\n{'='*60}")
            print(f"Lead #{lead.id}: {lead.title}")
            print(f"Trade: {lead.keyword} | Location: {lead.location}")
            
            # Generate AI response
            response = craft_contractor_response(lead)
            if not response:
                print("❌ Failed to generate response")
                continue
            
            # Post to Reddit
            success = post_to_reddit(lead, response, dry_run=dry_run)
            
            if success:
                # Mark as processed
                lead.ai_processed = True
                db.session.commit()
                print(f"✅ Lead #{lead.id} processed")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Actually post to Reddit')
    parser.add_argument('--limit', type=int, default=5, help='Max leads to process')
    args = parser.parse_args()
    
    dry_run = not args.live
    mode = "LIVE" if args.live else "DRY RUN"
    
    print(f"\n{'='*60}")
    print(f"AI CONTRACTOR RESPONSE AGENT - {mode}")
    print(f"{'='*60}")
    
    process_approved_leads(dry_run=dry_run, limit=args.limit)
