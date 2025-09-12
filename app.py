from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe
import os
import logging
import json
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=["https://lcherouri.github.io", "http://localhost:5173"])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Stripe with live keys
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Stripe Price IDs - These will be created in your Stripe dashboard
PRICE_IDS = {
    'starter_monthly': os.getenv('STRIPE_STARTER_MONTHLY_PRICE_ID'),
    'starter_yearly': os.getenv('STRIPE_STARTER_YEARLY_PRICE_ID'),
    'professional_monthly': os.getenv('STRIPE_PROFESSIONAL_MONTHLY_PRICE_ID'),
    'professional_yearly': os.getenv('STRIPE_PROFESSIONAL_YEARLY_PRICE_ID'),
}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'service': 'ReviewMaestro Payment API',
        'timestamp': datetime.utcnow().isoformat(),
        'stripe_configured': bool(stripe.api_key)
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get public configuration for frontend"""
    return jsonify({
        'stripe_publishable_key': os.getenv('STRIPE_PUBLISHABLE_KEY'),
        'api_url': request.host_url.rstrip('/')
    })

@app.route('/api/create-subscription', methods=['POST'])
def create_subscription():
    """Create a subscription with free trial"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'name', 'plan', 'billing_cycle', 'payment_method_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get the appropriate price ID
        plan_key = f"{data['plan']}_{data['billing_cycle']}"
        price_id = PRICE_IDS.get(plan_key)
        
        if not price_id:
            return jsonify({'error': f'Invalid plan or billing cycle: {plan_key}'}), 400
        
        # Create customer
        customer = stripe.Customer.create(
            email=data['email'],
            name=data['name'],
            payment_method=data['payment_method_id'],
            invoice_settings={'default_payment_method': data['payment_method_id']},
            metadata={
                'plan': data['plan'],
                'billing_cycle': data['billing_cycle'],
                'source': 'reviewmaestro_saas',
                'company': data.get('company', '')
            }
        )
        
        logger.info(f"Customer created: {customer.id} for {data['email']}")
        
        # Create subscription with trial
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': price_id}],
            trial_period_days=14,  # 14-day free trial
            expand=['latest_invoice.payment_intent'],
            metadata={
                'plan': data['plan'],
                'billing_cycle': data['billing_cycle']
            }
        )
        
        logger.info(f"Subscription created: {subscription.id} for customer {customer.id}")
        
        return jsonify({
            'subscription_id': subscription.id,
            'customer_id': customer.id,
            'client_secret': subscription.latest_invoice.payment_intent.client_secret if subscription.latest_invoice.payment_intent else None,
            'trial_end': subscription.trial_end,
            'status': subscription.status
        })
        
    except stripe.error.CardError as e:
        logger.error(f"Card error: {str(e)}")
        return jsonify({'error': f'Card error: {e.user_message}'}), 400
    except stripe.error.RateLimitError as e:
        logger.error(f"Rate limit error: {str(e)}")
        return jsonify({'error': 'Too many requests. Please try again later.'}), 429
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Invalid request: {str(e)}")
        return jsonify({'error': f'Invalid request: {str(e)}'}), 400
    except stripe.error.AuthenticationError as e:
        logger.error(f"Authentication error: {str(e)}")
        return jsonify({'error': 'Authentication failed. Please contact support.'}), 401
    except stripe.error.APIConnectionError as e:
        logger.error(f"Network error: {str(e)}")
        return jsonify({'error': 'Network error. Please try again.'}), 503
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return jsonify({'error': f'Payment processing error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

@app.route('/api/create-portal-session', methods=['POST'])
def create_portal_session():
    """Create a customer portal session for subscription management"""
    try:
        data = request.get_json()
        
        if 'customer_id' not in data:
            return jsonify({'error': 'Missing customer_id'}), 400
        
        session = stripe.billing_portal.Session.create(
            customer=data['customer_id'],
            return_url=data.get('return_url', 'https://lcherouri.github.io/reviewmaestro-saas/')
        )
        
        logger.info(f"Portal session created for customer: {data['customer_id']}")
        
        return jsonify({'url': session.url})
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return jsonify({'error': f'Stripe error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/api/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    if not endpoint_secret:
        logger.error("Webhook secret not configured")
        return 'Webhook secret not configured', 400

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return 'Invalid signature', 400

    # Handle the event
    event_type = event['type']
    data_object = event['data']['object']
    
    logger.info(f"Received webhook event: {event_type}")
    
    try:
        if event_type == 'customer.subscription.created':
            handle_subscription_created(data_object)
        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(data_object)
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(data_object)
        elif event_type == 'invoice.payment_succeeded':
            handle_payment_succeeded(data_object)
        elif event_type == 'invoice.payment_failed':
            handle_payment_failed(data_object)
        elif event_type == 'customer.subscription.trial_will_end':
            handle_trial_will_end(data_object)
        else:
            logger.info(f"Unhandled event type: {event_type}")
    except Exception as e:
        logger.error(f"Error handling webhook {event_type}: {str(e)}")
        return f'Error handling webhook: {str(e)}', 500

    return jsonify({'status': 'success'})

def handle_subscription_created(subscription):
    """Handle subscription creation"""
    logger.info(f"Subscription created: {subscription['id']}")
    # TODO: Send welcome email
    # TODO: Grant platform access
    # TODO: Update database

def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    logger.info(f"Subscription updated: {subscription['id']} - Status: {subscription['status']}")
    # TODO: Update subscription status in database
    # TODO: Handle plan changes

def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    logger.info(f"Subscription cancelled: {subscription['id']}")
    # TODO: Revoke platform access
    # TODO: Send cancellation confirmation
    # TODO: Update database

def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    logger.info(f"Payment succeeded: {invoice['id']} - Amount: {invoice['amount_paid']}")
    # TODO: Send payment confirmation
    # TODO: Extend subscription period
    # TODO: Update payment history

def handle_payment_failed(invoice):
    """Handle failed payment"""
    logger.info(f"Payment failed: {invoice['id']} - Customer: {invoice['customer']}")
    # TODO: Send payment failure notification
    # TODO: Implement retry logic
    # TODO: Update subscription status

def handle_trial_will_end(subscription):
    """Handle trial ending soon"""
    logger.info(f"Trial ending soon for subscription: {subscription['id']}")
    # TODO: Send trial ending reminder
    # TODO: Encourage conversion

@app.route('/api/subscription-status/<customer_id>', methods=['GET'])
def get_subscription_status(customer_id):
    """Get subscription status for a customer"""
    try:
        # Get customer's subscriptions
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status='all',
            limit=10
        )
        
        if not subscriptions.data:
            return jsonify({'status': 'no_subscription'})
        
        # Get the most recent subscription
        subscription = subscriptions.data[0]
        
        return jsonify({
            'subscription_id': subscription.id,
            'status': subscription.status,
            'current_period_start': subscription.current_period_start,
            'current_period_end': subscription.current_period_end,
            'trial_end': subscription.trial_end,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'plan': subscription.items.data[0].price.nickname if subscription.items.data else None
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return jsonify({'error': f'Stripe error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Validate required environment variables
    required_env_vars = [
        'STRIPE_SECRET_KEY',
        'STRIPE_PUBLISHABLE_KEY'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set the following environment variables:")
        for var in missing_vars:
            logger.error(f"  {var}")
        exit(1)
    
    # Validate Stripe configuration
    try:
        stripe.Account.retrieve()
        logger.info("Stripe configuration validated successfully")
    except stripe.error.AuthenticationError:
        logger.error("Invalid Stripe API key")
        exit(1)
    except Exception as e:
        logger.error(f"Error validating Stripe configuration: {str(e)}")
        exit(1)
    
    # Run the app
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting ReviewMaestro Payment API on port {port}")
    logger.info(f"CORS enabled for: https://lcherouri.github.io")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

