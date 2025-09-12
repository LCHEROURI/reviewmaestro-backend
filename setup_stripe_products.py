#!/usr/bin/env python3
"""
Script to create Stripe products and prices for ReviewMaestro SaaS
Run this script once to set up your Stripe products and get the price IDs
"""

import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def create_products_and_prices():
    """Create Stripe products and prices for ReviewMaestro"""
    
    print("🚀 Setting up Stripe products for ReviewMaestro SaaS...")
    print("=" * 60)
    
    try:
        # Create Starter Product
        print("📦 Creating Starter Plan product...")
        starter_product = stripe.Product.create(
            name="ReviewMaestro Starter",
            description="Perfect for single restaurants - Up to 100 reviews/month with AI analysis and response generation",
            metadata={
                "plan_type": "starter",
                "features": "100 reviews/month, AI sentiment analysis, Basic response templates, Email support"
            }
        )
        print(f"✅ Starter product created: {starter_product.id}")
        
        # Create Professional Product
        print("📦 Creating Professional Plan product...")
        professional_product = stripe.Product.create(
            name="ReviewMaestro Professional",
            description="For growing restaurants - Up to 1,000 reviews/month with advanced features and priority support",
            metadata={
                "plan_type": "professional",
                "features": "1,000 reviews/month, Advanced AI analysis, Custom response generation, Priority support, Analytics dashboard"
            }
        )
        print(f"✅ Professional product created: {professional_product.id}")
        
        # Create Prices for Starter Plan
        print("💰 Creating Starter Plan prices...")
        
        starter_monthly = stripe.Price.create(
            product=starter_product.id,
            unit_amount=1900,  # $19.00 in cents
            currency='usd',
            recurring={'interval': 'month'},
            nickname='Starter Monthly',
            metadata={'plan': 'starter', 'billing': 'monthly'}
        )
        print(f"✅ Starter Monthly price created: {starter_monthly.id}")
        
        starter_yearly = stripe.Price.create(
            product=starter_product.id,
            unit_amount=15600,  # $156.00 in cents (30% discount)
            currency='usd',
            recurring={'interval': 'year'},
            nickname='Starter Yearly',
            metadata={'plan': 'starter', 'billing': 'yearly'}
        )
        print(f"✅ Starter Yearly price created: {starter_yearly.id}")
        
        # Create Prices for Professional Plan
        print("💰 Creating Professional Plan prices...")
        
        professional_monthly = stripe.Price.create(
            product=professional_product.id,
            unit_amount=9900,  # $99.00 in cents
            currency='usd',
            recurring={'interval': 'month'},
            nickname='Professional Monthly',
            metadata={'plan': 'professional', 'billing': 'monthly'}
        )
        print(f"✅ Professional Monthly price created: {professional_monthly.id}")
        
        professional_yearly = stripe.Price.create(
            product=professional_product.id,
            unit_amount=82800,  # $828.00 in cents (30% discount)
            currency='usd',
            recurring={'interval': 'year'},
            nickname='Professional Yearly',
            metadata={'plan': 'professional', 'billing': 'yearly'}
        )
        print(f"✅ Professional Yearly price created: {professional_yearly.id}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! All products and prices created!")
        print("=" * 60)
        
        print("\n📋 ENVIRONMENT VARIABLES TO SET:")
        print("Copy these to your deployment environment:")
        print("-" * 40)
        print(f"STRIPE_STARTER_MONTHLY_PRICE_ID={starter_monthly.id}")
        print(f"STRIPE_STARTER_YEARLY_PRICE_ID={starter_yearly.id}")
        print(f"STRIPE_PROFESSIONAL_MONTHLY_PRICE_ID={professional_monthly.id}")
        print(f"STRIPE_PROFESSIONAL_YEARLY_PRICE_ID={professional_yearly.id}")
        
        print("\n📊 PRICING SUMMARY:")
        print("-" * 40)
        print("Starter Plan:")
        print(f"  Monthly: $19.00/month ({starter_monthly.id})")
        print(f"  Yearly:  $156.00/year ({starter_yearly.id}) - 30% savings!")
        print("\nProfessional Plan:")
        print(f"  Monthly: $99.00/month ({professional_monthly.id})")
        print(f"  Yearly:  $828.00/year ({professional_yearly.id}) - 30% savings!")
        
        print("\n🔗 NEXT STEPS:")
        print("-" * 40)
        print("1. Copy the price IDs above to your environment variables")
        print("2. Deploy your backend with these environment variables")
        print("3. Test the payment flow with test cards")
        print("4. Switch to live mode when ready!")
        
        return {
            'starter_monthly': starter_monthly.id,
            'starter_yearly': starter_yearly.id,
            'professional_monthly': professional_monthly.id,
            'professional_yearly': professional_yearly.id
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error: {str(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None

def verify_stripe_connection():
    """Verify Stripe API connection"""
    try:
        account = stripe.Account.retrieve()
        print(f"✅ Connected to Stripe account: {account.display_name or account.id}")
        print(f"📧 Account email: {account.email}")
        print(f"🌍 Country: {account.country}")
        print(f"💰 Currency: {account.default_currency.upper()}")
        return True
    except stripe.error.AuthenticationError:
        print("❌ Invalid Stripe API key. Please check your STRIPE_SECRET_KEY.")
        return False
    except Exception as e:
        print(f"❌ Error connecting to Stripe: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔑 ReviewMaestro Stripe Setup")
    print("=" * 60)
    
    # Check if API key is set
    if not os.getenv('STRIPE_SECRET_KEY'):
        print("❌ STRIPE_SECRET_KEY environment variable not set!")
        print("Please set your Stripe secret key and try again.")
        exit(1)
    
    # Verify connection
    if not verify_stripe_connection():
        exit(1)
    
    print("\n" + "=" * 60)
    
    # Create products and prices
    price_ids = create_products_and_prices()
    
    if price_ids:
        print(f"\n✅ Setup complete! Your ReviewMaestro SaaS is ready for payments!")
    else:
        print(f"\n❌ Setup failed. Please check the errors above and try again.")
        exit(1)

