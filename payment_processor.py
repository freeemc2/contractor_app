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
