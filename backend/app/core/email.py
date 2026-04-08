"""WILLIAM OS — Email Service"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import structlog

logger = structlog.get_logger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")


async def send_email(to: str, subject: str, body_html: str, body_text: str = "") -> bool:
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("email_not_configured")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"William OS <{SMTP_FROM}>"
        msg["To"] = to

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD.replace(" ", ""))
            server.sendmail(SMTP_FROM, to, msg.as_string())

        logger.info("email_sent", to=to, subject=subject)
        return True
    except Exception as e:
        logger.error("email_send_failed", error=str(e), to=to)
        return False


async def send_invite_email(to: str, invite_link: str, role: str, owner_name: str) -> bool:
    subject = f"You're invited to join {owner_name}'s William OS"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0f172a; color: #e2e8f0; padding: 40px; border-radius: 12px;">
        <h1 style="color: #3b82f6;">WILLIAM OS</h1>
        <h2>You've been invited</h2>
        <p>{owner_name} has invited you to join their William OS as a <strong>{role}</strong> member.</p>
        <a href="{invite_link}" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; margin: 20px 0;">
            Accept Invitation
        </a>
        <p style="color: #94a3b8; font-size: 14px;">If you didn't expect this, ignore this email.</p>
    </div>
    """
    body_text = f"You've been invited to William OS by {owner_name}. Accept here: {invite_link}"
    return await send_email(to, subject, body_html, body_text)


async def send_morning_briefing_email(to: str, name: str, briefing_text: str) -> bool:
    subject = f"Good morning {name} — Your William OS Briefing"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0f172a; color: #e2e8f0; padding: 40px; border-radius: 12px;">
        <h1 style="color: #3b82f6;">WILLIAM OS</h1>
        <h2>Morning Briefing</h2>
        <div style="background: #1e293b; padding: 20px; border-radius: 8px; line-height: 1.6;">
            {briefing_text.replace(chr(10), '<br>')}
        </div>
        <p style="color: #94a3b8; font-size: 12px; margin-top: 20px;">
            View full dashboard at <a href="https://williamos.duckdns.org" style="color: #3b82f6;">williamos.duckdns.org</a>
        </p>
    </div>
    """
    return await send_email(to, subject, body_html, briefing_text)
