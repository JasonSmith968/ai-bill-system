#!/usr/bin/env python3
"""
Stripe Production Setup and Verification.

Usage:
    python scripts/stripe_production.py --check          # Verify Stripe config
    python scripts/stripe_production.py --create-plans   # Create Stripe products/prices
    python scripts/stripe_production.py --test-webhook   # Test webhook endpoint
    python scripts/stripe_production.py --test-subscription  # Create test subscription
    python scripts/stripe_production.py --full-setup     # Run all setup steps

Requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in environment.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STRIPE_PLANS = [
    {
        "name": "AI Accounting — Free",
        "price_id_env": "STRIPE_PRICE_FREE",
        "amount": 0,
        "interval": "month",
        "description": "Free tier with basic features",
    },
    {
        "name": "AI Accounting — Pro Monthly",
        "price_id_env": "STRIPE_PRICE_PRO_MONTHLY",
        "amount": 2900,  # $29.00
        "interval": "month",
        "description": "Pro plan — monthly billing",
    },
    {
        "name": "AI Accounting — Pro Yearly",
        "price_id_env": "STRIPE_PRICE_PRO_YEARLY",
        "amount": 29000,  # $290.00
        "interval": "year",
        "description": "Pro plan — yearly billing (save 16%)",
    },
    {
        "name": "AI Accounting — Enterprise Monthly",
        "price_id_env": "STRIPE_PRICE_ENTERPRISE_MONTHLY",
        "amount": 9900,  # $99.00
        "interval": "month",
        "description": "Enterprise plan — monthly billing",
    },
]

WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "charge.refunded",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env():
    """Load .env.production into os.environ."""
    env_path = Path(__file__).resolve().parent.parent / ".env.production"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def get_stripe_key():
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        print("[ERROR] STRIPE_SECRET_KEY not set")
        print("  Set it in .env.production or export STRIPE_SECRET_KEY=sk_live_...")
        sys.exit(1)
    return key


def stripe_request(method, path, data=None):
    """Make a Stripe API request using stdlib only."""
    key = get_stripe_key()
    url = f"https://api.stripe.com/v1{path}"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    body = None
    if data:
        body = "&".join(f"{k}={v}" for k, v in data.items()).encode()

    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except URLError as e:
        if hasattr(e, "read"):
            error_body = json.loads(e.read())
            print(f"[ERROR] Stripe API: {error_body.get('error', {}).get('message', str(e))}")
        else:
            print(f"[ERROR] Stripe API: {e}")
        return None


def get_webhook_url():
    """Construct webhook URL from domain."""
    domain = os.environ.get("CORS_ORIGINS", "").replace("https://", "").replace("http://", "")
    if not domain or domain == "your-domain.com":
        domain = os.environ.get("FRONTEND_URL", "").replace("https://", "").replace("http://", "")
    if not domain or domain == "your-domain.com":
        print("[ERROR] Cannot determine domain. Set CORS_ORIGINS or FRONTEND_URL in .env.production")
        return None
    return f"https://{domain}/api/billing/webhook"


# ---------------------------------------------------------------------------
# Check Stripe Configuration
# ---------------------------------------------------------------------------

def cmd_check(args):
    """Verify Stripe configuration."""
    print("━━━ Stripe Configuration Check ━━━\n")

    load_env()

    # Check keys
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    if not secret_key:
        print("  [FAIL] STRIPE_SECRET_KEY not set")
    elif secret_key.startswith("sk_live_"):
        print("  [PASS] STRIPE_SECRET_KEY: live mode")
    elif secret_key.startswith("sk_test_"):
        print("  [WARN] STRIPE_SECRET_KEY: test mode (not production)")
    else:
        print("  [FAIL] STRIPE_SECRET_KEY: unknown format")

    if not webhook_secret:
        print("  [FAIL] STRIPE_WEBHOOK_SECRET not set")
    elif webhook_secret.startswith("whsec_"):
        print("  [PASS] STRIPE_WEBHOOK_SECRET: valid format")
    else:
        print("  [WARN] STRIPE_WEBHOOK_SECRET: unexpected format")

    # Check price IDs
    for plan in STRIPE_PLANS:
        price_id = os.environ.get(plan["price_id_env"], "")
        if price_id:
            print(f"  [PASS] {plan['price_id_env']}: {price_id}")
        else:
            print(f"  [WARN] {plan['price_id_env']}: not set")

    # Test API connection
    print("\n  Testing Stripe API connection...")
    result = stripe_request("GET", "/balance")
    if result:
        available = result.get("available", [{}])[0].get("amount", 0)
        currency = result.get("available", [{}])[0].get("currency", "usd")
        print(f"  [PASS] Stripe API connected. Balance: {available/100:.2f} {currency.upper()}")
    else:
        print("  [FAIL] Cannot connect to Stripe API")


# ---------------------------------------------------------------------------
# Create Stripe Products and Prices
# ---------------------------------------------------------------------------

def cmd_create_plans(args):
    """Create Stripe products and prices."""
    print("━━━ Create Stripe Products & Prices ━━━\n")

    load_env()

    results = []
    for plan in STRIPE_PLANS:
        print(f"  Creating: {plan['name']}...")

        # Create product
        product = stripe_request("POST", "/products", {
            "name": plan["name"],
            "description": plan["description"],
        })
        if not product:
            print(f"    [FAIL] Could not create product")
            continue

        product_id = product["id"]
        print(f"    Product: {product_id}")

        # Create price (skip free tier)
        if plan["amount"] > 0:
            price = stripe_request("POST", "/prices", {
                "product": product_id,
                "unit_amount": str(plan["amount"]),
                "currency": "usd",
                "recurring[interval]": plan["interval"],
            })
            if price:
                price_id = price["id"]
                print(f"    Price: {price_id} (${plan['amount']/100:.2f}/{plan['interval']})")
                results.append({
                    "name": plan["name"],
                    "product_id": product_id,
                    "price_id": price_id,
                    "env_var": plan["price_id_env"],
                })
            else:
                print(f"    [FAIL] Could not create price")
        else:
            print(f"    Free tier — no price needed")
            results.append({
                "name": plan["name"],
                "product_id": product_id,
                "price_id": "free",
                "env_var": plan["price_id_env"],
            })

    # Output summary
    print("\n━━━ Summary ━━━")
    print("\nAdd these to .env.production:\n")
    for r in results:
        if r["price_id"] != "free":
            print(f"  {r['env_var']}={r['price_id']}")

    print(f"\nCreated {len(results)} products.")


# ---------------------------------------------------------------------------
# Test Webhook
# ---------------------------------------------------------------------------

def cmd_test_webhook(args):
    """Test the webhook endpoint."""
    print("━━━ Test Webhook Endpoint ━━━\n")

    load_env()

    webhook_url = get_webhook_url()
    if not webhook_url:
        return

    print(f"  Webhook URL: {webhook_url}")

    # Check if endpoint is reachable
    try:
        req = Request(webhook_url, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Stripe-Signature", "test")
        with urlopen(req, timeout=10) as resp:
            print(f"  [PASS] Endpoint reachable (HTTP {resp.status})")
    except URLError as e:
        if hasattr(e, "code"):
            if e.code == 400:
                print(f"  [PASS] Endpoint reachable (HTTP 400 — expected for invalid signature)")
            else:
                print(f"  [WARN] Endpoint returned HTTP {e.code}")
        else:
            print(f"  [FAIL] Endpoint not reachable: {e}")

    # Check Stripe webhook configuration
    print("\n  Checking Stripe webhook endpoints...")
    webhooks = stripe_request("GET", "/webhook_endpoints")
    if webhooks and "data" in webhooks:
        found = False
        for wh in webhooks["data"]:
            if webhook_url in wh.get("url", ""):
                found = True
                print(f"  [PASS] Webhook endpoint registered: {wh['id']}")
                print(f"    Status: {wh.get('status', 'unknown')}")
                print(f"    Events: {len(wh.get('enabled_events', []))}")
                break
        if not found:
            print(f"  [WARN] No webhook endpoint found for {webhook_url}")
            print(f"  Register at: https://dashboard.stripe.com/webhooks")
    else:
        print("  [WARN] Could not list webhook endpoints")


# ---------------------------------------------------------------------------
# Test Subscription
# ---------------------------------------------------------------------------

def cmd_test_subscription(args):
    """Create a test subscription to verify the flow."""
    print("━━━ Test Subscription Flow ━━━\n")

    load_env()

    # Create test customer
    print("  Creating test customer...")
    customer = stripe_request("POST", "/customers", {
        "email": "test-subscription@example.com",
        "name": "Test Subscription",
        "metadata[test]": "true",
    })
    if not customer:
        print("  [FAIL] Could not create test customer")
        return

    customer_id = customer["id"]
    print(f"  Customer: {customer_id}")

    # Find a price to subscribe to
    pro_monthly = os.environ.get("STRIPE_PRICE_PRO_MONTHLY", "")
    if not pro_monthly:
        print("  [WARN] STRIPE_PRICE_PRO_MONTHLY not set — skipping subscription test")
        return

    # Create subscription
    print("  Creating test subscription...")
    subscription = stripe_request("POST", "/subscriptions", {
        "customer": customer_id,
        "items[0][price]": pro_monthly,
        "payment_behavior": "default_incomplete",
        "expand[0]": "latest_invoice.payment_intent",
    })
    if subscription:
        print(f"  [PASS] Subscription created: {subscription['id']}")
        print(f"    Status: {subscription.get('status', 'unknown')}")
    else:
        print("  [FAIL] Could not create subscription")

    # Cleanup: delete test customer
    print("\n  Cleaning up test customer...")
    stripe_request("DELETE", f"/customers/{customer_id}")
    print("  Test customer deleted")


# ---------------------------------------------------------------------------
# Full Setup
# ---------------------------------------------------------------------------

def cmd_full_setup(args):
    """Run all setup steps."""
    print("━━━ Full Stripe Production Setup ━━━\n")

    cmd_check(args)
    print("\n" + "=" * 60 + "\n")

    cmd_create_plans(args)
    print("\n" + "=" * 60 + "\n")

    cmd_test_webhook(args)
    print("\n" + "=" * 60 + "\n")

    cmd_test_subscription(args)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stripe production setup and verification."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Verify Stripe config")
    group.add_argument("--create-plans", action="store_true", help="Create products/prices")
    group.add_argument("--test-webhook", action="store_true", help="Test webhook endpoint")
    group.add_argument("--test-subscription", action="store_true", help="Test subscription flow")
    group.add_argument("--full-setup", action="store_true", help="Run all setup steps")

    args = parser.parse_args()

    if args.check:
        cmd_check(args)
    elif args.create_plans:
        cmd_create_plans(args)
    elif args.test_webhook:
        cmd_test_webhook(args)
    elif args.test_subscription:
        cmd_test_subscription(args)
    elif args.full_setup:
        cmd_full_setup(args)


if __name__ == "__main__":
    main()
