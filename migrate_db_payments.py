import sqlite3
conn = sqlite3.connect('instance/contractor_leads.db')
cols = ["response_status TEXT DEFAULT 'pending'", "conversation_history TEXT", "deposit_amount DECIMAL(10,2)", 
        "deposit_paid_at DATETIME", "stripe_session_id TEXT", "total_job_cost DECIMAL(10,2)", 
        "platform_fee_amount DECIMAL(10,2)", "contractor_payout_amount DECIMAL(10,2)"]
for col in cols:
    try:
        conn.execute(f"ALTER TABLE leads ADD COLUMN {col}")
        print(f"✅ Added: {col.split()[0]}")
    except:
        print(f"⏭️  Skipped: {col.split()[0]}")
conn.commit()
conn.close()
print("✅ Migration complete!")
