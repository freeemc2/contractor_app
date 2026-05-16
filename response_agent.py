#!/usr/bin/env python3
import os, sys, time, json, sqlite3
from datetime import datetime
from anthropic import Anthropic
from payment_processor import PaymentProcessor

try:
    import praw
    REDDIT_OK = True
except:
    REDDIT_OK = False
    print("⚠️  praw not installed")

class AIResponseAgent:
    def __init__(self):
        self.db = 'instance/contractor_leads.db'
        self.claude = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY')) if os.getenv('ANTHROPIC_API_KEY') else None
        self.payment = PaymentProcessor()
        self.count = 0
        
    def get_pending(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute("SELECT id, reddit_post_id, title, body, detected_trade, location FROM leads WHERE (response_status IS NULL OR response_status='pending') AND reddit_post_id IS NOT NULL LIMIT 10")
        return [{'id': r[0], 'reddit_post_id': r[1], 'title': r[2], 'body': r[3], 'trade': r[4], 'location': r[5]} for r in c.fetchall()]
    
    def send_payments(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute("SELECT id, title FROM leads WHERE response_status='qualified'")
        for lid, title in c.fetchall():
            result = self.payment.create_deposit_link(lid, 800, title[:50])
            if result:
                conn.execute("UPDATE leads SET response_status='deposit_sent', deposit_payment_link=?, deposit_amount=?, estimated_job_cost=800 WHERE id=?", 
                           (result['payment_url'], result['deposit_amount'], lid))
                print(f"💳 Lead #{lid}: ${result['deposit_amount']} deposit")
                print(f"   Link: {result['payment_url']}")
        conn.commit()
    
    def check_paid(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute("SELECT id, title, deposit_amount FROM leads WHERE response_status='deposit_paid'")
        paid = c.fetchall()
        if paid:
            print(f"\n💰 {len(paid)} PAID DEPOSITS:")
            for lid, title, amt in paid:
                print(f"   #{lid}: {title[:40]} - ${amt}")
    
    def run(self):
        print(f"\n{'='*50}\n🤖 AI Agent - {datetime.now().strftime('%H:%M:%S')}\n{'='*50}")
        
        # Show pending
        pending = self.get_pending()
        if pending:
            print(f"\n📋 {len(pending)} pending leads")
            for lead in pending[:5]:
                print(f"   #{lead['id']}: {lead['title'][:50]}")
        
        # Send payment links
        self.send_payments()
        
        # Show paid
        self.check_paid()
        
        # Stats
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute("SELECT response_status, COUNT(*) FROM leads GROUP BY response_status")
        print(f"\n📊 Database:")
        for status, count in c.fetchall():
            print(f"   {status or 'pending'}: {count}")

if __name__ == '__main__':
    agent = AIResponseAgent()
    agent.run()
