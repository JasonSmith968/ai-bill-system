"""Email service — SMTP with development console fallback.

Production: requires SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD.
Development: falls back to console output if SMTP is not configured.

Environment variables:
    SMTP_HOST          — SMTP server hostname (e.g. smtp.qq.com, smtp.gmail.com)
    SMTP_PORT          — SMTP server port (default 587 for STARTTLS, 465 for SSL)
    SMTP_USERNAME      — SMTP login username (usually the sender email)
    SMTP_PASSWORD      — SMTP login password or authorisation code
    SMTP_FROM_EMAIL    — "From" address (defaults to SMTP_USERNAME)
    SMTP_FROM_NAME     — "From" display name (default "AI 智能记账")
    SMTP_USE_TLS       — "true" for STARTTLS (default), "false" for SSL
    SMTP_USE_SSL       — "true" for SSL (port 465), "false" otherwise
    FLASK_ENV          — "production" forces real SMTP; anything else allows console fallback
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

logger = logging.getLogger(__name__)
biz_logger = logging.getLogger('business')


def _smtp_configured():
    """Check whether the minimum SMTP environment variables are set."""
    return all([
        os.environ.get('SMTP_HOST'),
        os.environ.get('SMTP_USERNAME'),
        os.environ.get('SMTP_PASSWORD'),
    ])


def _is_production():
    """Check if running in production mode."""
    return os.environ.get('FLASK_ENV', '').lower() == 'production'


class EmailService:
    """Pluggable email service with SMTP transport and console fallback.

    In development (FLASK_ENV != production), if SMTP is not configured the
    email content is logged to the console so registration / password reset
    flows remain usable during local development.

    In production (FLASK_ENV == production), SMTP configuration is mandatory.
    Missing configuration raises RuntimeError so the operator notices immediately.
    """

    @staticmethod
    def send(to_email, subject, body, html=None):
        """Send an email.

        Args:
            to_email: Recipient email address.
            subject:  Email subject line.
            body:     Plain-text body.
            html:     Optional HTML body. If provided, the email is sent as
                      multipart/alternative with both text and HTML parts.

        Returns:
            True on success, False on failure.

        Raises:
            RuntimeError: In production mode when SMTP is not configured.
        """
        if not _smtp_configured():
            if _is_production():
                raise RuntimeError(
                    'SMTP not configured. Set SMTP_HOST, SMTP_USERNAME, '
                    'SMTP_PASSWORD in .env.production. '
                    'See .env.production.example for reference.'
                )
            # Development fallback: log to console
            biz_logger.info(f"EMAIL (console fallback) -> {to_email} | Subject: {subject}")
            print(f"\n{'='*60}")
            print(f"EMAIL TO: {to_email}")
            print(f"SUBJECT: {subject}")
            if html:
                print(f"BODY (HTML):\n{html[:500]}...")
            else:
                print(f"BODY:\n{body}")
            print(f"{'='*60}\n")
            return True

        # Real SMTP send
        smtp_host = os.environ['SMTP_HOST']
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        smtp_username = os.environ['SMTP_USERNAME']
        smtp_password = os.environ['SMTP_PASSWORD']
        from_email = os.environ.get('SMTP_FROM_EMAIL', smtp_username)
        from_name = os.environ.get('SMTP_FROM_NAME', 'AI 智能记账')
        use_tls = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
        use_ssl = os.environ.get('SMTP_USE_SSL', 'false').lower() == 'true'

        # Build message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = formataddr((from_name, from_email))
        msg['To'] = to_email

        # Always attach plain-text part
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Optionally attach HTML part
        if html:
            msg.attach(MIMEText(html, 'html', 'utf-8'))

        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                if use_tls:
                    server.starttls()

            server.login(smtp_username, smtp_password)
            server.sendmail(from_email, [to_email], msg.as_string())
            server.quit()

            biz_logger.info(f"EMAIL sent -> {to_email} | Subject: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            biz_logger.error(f"EMAIL auth failed -> {to_email} | {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending to {to_email}: {e}")
            biz_logger.error(f"EMAIL failed -> {to_email} | {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected email error: {e}", exc_info=True)
            biz_logger.error(f"EMAIL error -> {to_email} | {e}")
            return False

    @staticmethod
    def send_password_reset(to_email, reset_link):
        """Send password reset email."""
        subject = "AI 智能记账 - 密码重置"
        body = (
            f"您好，\n\n"
            f"请点击以下链接重置密码（1小时内有效）：\n\n"
            f"{reset_link}\n\n"
            f"如非本人操作，请忽略此邮件。您的账号安全不会受到影响。\n\n"
            f"AI 智能记账系统"
        )
        html = f"""
        <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">AI 智能记账 - 密码重置</h2>
            <p>您好，</p>
            <p>请点击以下按钮重置密码（<strong>1小时内有效</strong>）：</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}"
                   style="background-color: #2563eb; color: white; padding: 12px 30px;
                          text-decoration: none; border-radius: 6px; font-size: 16px;">
                    重置密码
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">
                如果按钮无法点击，请复制以下链接到浏览器打开：<br>
                <a href="{reset_link}">{reset_link}</a>
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 12px;">
                如非本人操作，请忽略此邮件。您的账号安全不会受到影响。
            </p>
        </div>
        """
        return EmailService.send(to_email, subject, body, html=html)

    @staticmethod
    def send_email_verification(to_email, verify_link):
        """Send email verification link."""
        subject = "AI 智能记账 - 邮箱验证"
        body = (
            f"您好，\n\n"
            f"感谢注册 AI 智能记账系统！请点击以下链接验证您的邮箱（24小时内有效）：\n\n"
            f"{verify_link}\n\n"
            f"如非本人操作，请忽略此邮件。\n\n"
            f"AI 智能记账系统"
        )
        html = f"""
        <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">AI 智能记账 - 邮箱验证</h2>
            <p>您好，</p>
            <p>感谢注册 AI 智能记账系统！请点击以下按钮验证您的邮箱（<strong>24小时内有效</strong>）：</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{verify_link}"
                   style="background-color: #10b981; color: white; padding: 12px 30px;
                          text-decoration: none; border-radius: 6px; font-size: 16px;">
                    验证邮箱
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">
                如果按钮无法点击，请复制以下链接到浏览器打开：<br>
                <a href="{verify_link}">{verify_link}</a>
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 12px;">
                如非本人操作，请忽略此邮件。
            </p>
        </div>
        """
        return EmailService.send(to_email, subject, body, html=html)
