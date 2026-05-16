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
