#!/usr/bin/env python3
"""Test email sending via SMTP.

Usage:
    # Check SMTP configuration (no email sent):
    python scripts/test_email.py --check

    # Send a real test email:
    python scripts/test_email.py --to your-email@example.com

    # Send to yourself (uses SMTP_USERNAME):
    python scripts/test_email.py --self

Environment:
    Reads SMTP configuration from .env file (loaded via python-dotenv).
"""

import os
import sys
import argparse

# Fix Windows console encoding for emoji output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def check_config():
    """Print SMTP configuration status (no secrets)."""
    print("=" * 50)
    print("SMTP Configuration Check")
    print("=" * 50)

    vars_info = [
        ('SMTP_HOST', True),
        ('SMTP_PORT', False),
        ('SMTP_USERNAME', True),
        ('SMTP_PASSWORD', True),
        ('SMTP_FROM_EMAIL', False),
        ('SMTP_FROM_NAME', False),
        ('SMTP_USE_TLS', False),
        ('SMTP_USE_SSL', False),
        ('FLASK_ENV', False),
    ]

    all_ok = True
    for var, required in vars_info:
        value = os.environ.get(var, '')
        if var == 'SMTP_PASSWORD':
            display = '******' if value else '(not set)'
        else:
            display = value if value else '(not set)'

        status = '✅' if value else ('❌ MISSING' if required else '⚠️  optional, using default')
        if required and not value:
            all_ok = False

        print(f"  {var}: {display}  {status}")

    print()
    flask_env = os.environ.get('FLASK_ENV', 'development')
    if flask_env == 'production' and not all_ok:
        print("❌ PRODUCTION MODE: Missing required SMTP config!")
        print("   Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD in .env.production")
        return False
    elif not all_ok:
        print("⚠️  Development mode: emails will be printed to console.")
        return True
    else:
        print("✅ All SMTP config present.")
        return True


def send_test(to_email):
    """Send a test email."""
    from utils.email_service import EmailService

    print(f"\nSending test email to: {to_email}")
    print(f"SMTP Host: {os.environ.get('SMTP_HOST', '(not set)')}")
    print()

    result = EmailService.send(
        to_email=to_email,
        subject="AI 智能记账 - 邮件服务测试",
        body=(
            "这是一封测试邮件。\n\n"
            "如果您收到此邮件，说明 SMTP 邮件服务配置正确！\n\n"
            "AI 智能记账系统"
        ),
        html="""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">✅ 邮件服务测试成功</h2>
            <p>如果您看到此邮件，说明 SMTP 配置正确。</p>
            <p style="color: #666; font-size: 14px;">AI 智能记账系统</p>
        </div>
        """
    )

    if result:
        print("✅ Email sent successfully!")
    else:
        print("❌ Failed to send email. Check SMTP configuration and logs.")

    return result


def main():
    parser = argparse.ArgumentParser(description='Test SMTP email service')
    parser.add_argument('--check', action='store_true', help='Check SMTP configuration only')
    parser.add_argument('--to', type=str, help='Recipient email address')
    parser.add_argument('--self', action='store_true', help='Send to SMTP_USERNAME')

    args = parser.parse_args()

    if args.check:
        ok = check_config()
        sys.exit(0 if ok else 1)

    if args.self:
        to_email = os.environ.get('SMTP_USERNAME', '')
        if not to_email:
            print("❌ SMTP_USERNAME not set. Cannot send to self.")
            sys.exit(1)
    elif args.to:
        to_email = args.to
    else:
        parser.print_help()
        print("\n💡 Usage: python scripts/test_email.py --to your-email@example.com")
        sys.exit(1)

    # Check config first
    if not check_config():
        sys.exit(1)

    print()
    send_test(to_email)


if __name__ == '__main__':
    main()
