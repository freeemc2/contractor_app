#!/bin/bash
set -e
echo "🚀 Deploying Stripe Payment Integration..."
cd /var/www/contractor_app

# 1. Create payment processor
cat > payment_processor.py << 'PROCESSOR_EOF'
#!/usr/bin/env python3
import os
import stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe
    
    def calculate_deposit(self, estimated_cost):
        if not estimated_cost or estimated_cost < 200:
            return 50.00
        deposit = round(estimated_cost * 0.20, 2)
        return min(max(deposit, 50.00), 500.00)
    
    def create_deposit_link(self, lead_id, estimated_cost, job_description, customer_email=None):
        deposit_amount = self.calculate_deposit(estimated_cost)
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'Job Deposit - {job_description[:50]}',
                            'description': 'Refundable deposit to secure appointment.',
                        },
                        'unit_amount': int(deposit_amount * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f'http://82.25.74.217:5003/payment/success?session_id={{CHECKOUT_SESSION_ID}}&lead_id={lead_id}',
                cancel_url=f'http://82.25.74.217:5003/payment/cancel?lead_id={lead_id}',
                customer_email=customer_email,
                metadata={'lead_id': lead_id, 'payment_type': 'deposit', 'estimated_cost': estimated_cost}
            )
            return {'payment_url': session.url, 'session_id': session.id, 'deposit_amount': deposit_amount}
        except Exception as e:
            print(f"❌ Stripe error: {e}")
            return None
    
    def calculate_platform_fee(self, total_cost):
        commission = round(total_cost * 0.10, 2)
        admin_fee = round(total_cost * 0.10, 2)
        return {'commission': commission, 'admin_fee': admin_fee, 'total_fee': commission + admin_fee, 'contractor_payout': total_cost - commission - admin_fee}
PROCESSOR_EOF

# 2. Create payment routes
cat > payment_routes.py << 'ROUTES_EOF'
from flask import request, render_template_string
import sqlite3, stripe
from datetime import datetime

def add_payment_routes(app):
    @app.route('/payment/success')
    def payment_success():
        session_id, lead_id = request.args.get('session_id'), request.args.get('lead_id')
        if not session_id or not lead_id:
            return "Invalid payment", 400
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                conn = sqlite3.connect('instance/contractor_leads.db')
                conn.execute("UPDATE leads SET response_status='deposit_paid', deposit_paid_at=?, stripe_session_id=?, deposit_amount=? WHERE id=?",
                            (datetime.now(), session_id, session.amount_total/100, lead_id))
                conn.commit()
                conn.close()
                return render_template_string('<h1>✓ Payment Successful!</h1><p>Deposit: ${{ amt }}</p>', amt=f"{session.amount_total/100:.2f}")
        except Exception as e:
            return f"Error: {e}", 500
    
    @app.route('/payment/cancel')
    def payment_cancel():
        return '<h1>✗ Payment Cancelled</h1><p>No charges made.</p>'
ROUTES_EOF

# 3. Database migration
cat > migrate_db_payments.py << 'MIGRATE_EOF'
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
MIGRATE_EOF

# 4. Install with --break-system-packages (Kali requirement)
echo "📦 Installing dependencies..."
pip3 install stripe --break-system-packages -q

# 5. Run migration
python3 migrate_db_payments.py

# 6. Update app.py
if ! grep -q "add_payment_routes" app.py; then
    cp app.py app.py.backup
    sed -i '1a from payment_routes import add_payment_routes' app.py
    sed -i '/app = Flask/a add_payment_routes(app)' app.py
    echo "✅ Updated app.py"
fi

# 7. Test
python3 -c "from payment_processor import PaymentProcessor; p=PaymentProcessor(); print('Deposit \$1000 job:', p.calculate_deposit(1000)); print('Fee 20%:', p.calculate_platform_fee(1000)['total_fee'])"

# 8. Restart
pkill -f "python.*app.py" 2>/dev/null || true
echo "✅ DEPLOYED! Start app: python3 app.py"
