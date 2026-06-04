"""Stripe payment service wrapper."""

import stripe
from flask import current_app


def _get_stripe():
    """Configure and return stripe module."""
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY', '')
    return stripe


def create_customer(user):
    """Create a Stripe customer for a user."""
    s = _get_stripe()
    customer = s.Customer.create(
        email=user.email,
        name=user.username,
        metadata={'user_id': str(user.id)}
    )
    return customer


def create_checkout_session(customer_id, price_id, success_url, cancel_url):
    """Create a Stripe Checkout Session."""
    s = _get_stripe()
    session = s.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        line_items=[{
            'price': price_id,
            'quantity': 1,
        }],
        mode='subscription',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={'customer_id': customer_id}
    )
    return session


def create_portal_session(customer_id, return_url):
    """Create a Stripe Customer Portal session for managing subscription."""
    s = _get_stripe()
    session = s.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url
    )
    return session


def construct_webhook_event(payload, sig_header):
    """Verify and construct a Stripe webhook event."""
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET', '')
    if not webhook_secret:
        raise ValueError('Stripe webhook secret not configured')
    s = _get_stripe()
    return s.Webhook.construct_event(payload, sig_header, webhook_secret)


def cancel_subscription(stripe_sub_id):
    """Cancel a Stripe subscription immediately."""
    s = _get_stripe()
    return s.Subscription.delete(stripe_sub_id)


def get_subscription(stripe_sub_id):
    """Retrieve a Stripe subscription."""
    s = _get_stripe()
    return s.Subscription.retrieve(stripe_sub_id)


def get_customer(customer_id):
    """Retrieve a Stripe customer."""
    s = _get_stripe()
    return stripe.Customer.retrieve(customer_id)
