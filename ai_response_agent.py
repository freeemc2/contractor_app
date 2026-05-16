#!/usr/bin/env python3
"""
AI Response Agent - FREE & OPEN SOURCE
- Uses Ollama (local, no API costs)
- Uses praw (Reddit API, free)
- Responds to contractor leads
- Qualifies leads through conversation
"""
import os, sys, time, json, sqlite3, subprocess
from datetime import datetime

try:
    import praw
    REDDIT_OK = True
except:
    REDDIT_OK = False
    print("⚠️  praw not installed - run: pip3 install praw --break-system-packages")
    sys.exit(1)

class AIResponseAgent:
    def __init__(self):
        self.db = 'instance/contractor_leads.db'
        self.model = 'llama3.2:3b'
        
        # Reddit API - FREE (get credentials at reddit.com/prefs/apps)
        self.reddit = None  # Will set up with your credentials
        
    def get_pending_leads(self, limit=10):
        """Get leads that need AI responses"""
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute("""
            SELECT id, source_url, title, description, post_text, keyword, location 
            FROM leads 
            WHERE source_url IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        
        leads = []
        for row in c.fetchall():
            leads.append({
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'description': row[3],
                'post_text': row[4],
                'trade': row[5],
                'location': row[6]
            })
        return leads
    
    def ask_ollama(self, prompt):
        """Use Ollama (FREE, local) to generate response"""
        try:
            result = subprocess.run(
                ['ollama', 'run', self.model, prompt],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout.strip()
        except Exception as e:
            print(f"Ollama error: {e}")
            return None
    
    def craft_response(self, lead):
        """Craft personalized response using AI"""
        prompt = f"""You are a professional contractor service assistant. 

A homeowner posted this on Reddit:
Title: {lead['title']}
Post: {lead['description'][:300]}

They need help with: {lead['trade']}
Location: {lead['location']}

Write a brief, helpful response (2-3 sentences) that:
1. Acknowledges their need
2. Offers to connect them with licensed contractors
3. Asks when they need the work done
4. Sounds friendly and professional, not salesy

Keep it under 100 words. Do NOT include your role description in the response."""

        response = self.ask_ollama(prompt)
        return response
    
    def post_to_reddit(self, lead, response_text):
        """Post AI-generated response to Reddit (requires Reddit API setup)"""
        if not self.reddit:
            print("⚠️  Reddit API not configured yet")
            print(f"   Would post to: {lead['url']}")
            print(f"   Response: {response_text}")
            return False
        
        # TODO: Implement Reddit posting with praw
        # This requires Reddit API credentials
        return True
    
    def run(self, dry_run=True):
        """Main agent loop"""
        print(f"\n{'='*60}")
        print(f"🤖 AI Response Agent - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        print(f"Model: {self.model} (Ollama - FREE)")
        print(f"Mode: {'DRY RUN (testing)' if dry_run else 'LIVE (posting to Reddit)'}")
        
        # Get pending leads
        leads = self.get_pending_leads(limit=5)
        print(f"\n📋 Processing {len(leads)} leads...")
        
        for i, lead in enumerate(leads, 1):
            print(f"\n--- Lead #{lead['id']} ({i}/{len(leads)}) ---")
            print(f"Title: {lead['title'][:60]}...")
            print(f"Trade: {lead['trade']} | Location: {lead['location']}")
            
            # Generate AI response
            print("🤖 Generating response...")
            response = self.craft_response(lead)
            
            if response:
                print(f"\n✅ Generated response:")
                print(f"   {response}")
                
                if not dry_run:
                    # Post to Reddit (when configured)
                    self.post_to_reddit(lead, response)
            else:
                print("❌ Failed to generate response")
            
            time.sleep(2)  # Rate limiting
        
        print(f"\n{'='*60}")
        print(f"✅ Processed {len(leads)} leads")
        print(f"{'='*60}\n")

if __name__ == '__main__':
    agent = AIResponseAgent()
    agent.run(dry_run=True)  # Start in test mode
