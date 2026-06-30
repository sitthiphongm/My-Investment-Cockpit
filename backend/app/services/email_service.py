"""Email service for sending alert notifications."""

import logging
import smtplib
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications when alerts trigger."""

    @staticmethod
    def send_alert_email(
        to_email: str,
        stock_symbol: str,
        alert_type: str,
        target_price: Decimal,
        current_price: Decimal,
        note: Optional[str] = None,
    ) -> bool:
        """Send an email notification when a price alert triggers.

        Args:
            to_email: Recipient email address.
            stock_symbol: The stock that triggered the alert.
            alert_type: "Above" or "Below".
            target_price: The user's target price.
            current_price: The current market price that triggered the alert.
            note: Optional user note on the alert.

        Returns:
            True if email sent successfully, False otherwise.
        """
        if not settings.alert_email_enabled:
            logger.debug("Alert email disabled, skipping notification")
            return False

        if not settings.smtp_host or not settings.smtp_user:
            logger.warning("SMTP not configured, cannot send alert email")
            return False

        subject = f"🔔 Price Alert Triggered: {stock_symbol} {alert_type} ${target_price}"

        direction = "risen above" if alert_type == "Above" else "dropped below"
        html_body = f"""
        <html>
        <body style="font-family: 'DM Sans', Arial, sans-serif; padding: 20px; background-color: #F4F6F9;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
                <h1 style="color: #1a202c; margin-top: 0;">🔔 Price Alert Triggered</h1>
                <p style="color: #475569; font-size: 16px;">
                    Your price alert for <strong style="color: #0052FF;">{stock_symbol}</strong> has been triggered.
                </p>
                <div style="background: #F4F6F9; border-radius: 12px; padding: 20px; margin: 20px 0;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #64748B; font-size: 14px;">Stock Symbol</td>
                            <td style="padding: 8px 0; font-weight: 700; color: #1a202c; text-align: right;">{stock_symbol}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #64748B; font-size: 14px;">Alert Type</td>
                            <td style="padding: 8px 0; font-weight: 700; color: #1a202c; text-align: right;">{alert_type} (price {direction} target)</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #64748B; font-size: 14px;">Target Price</td>
                            <td style="padding: 8px 0; font-weight: 700; color: #0052FF; text-align: right;">${target_price}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #64748B; font-size: 14px;">Current Price</td>
                            <td style="padding: 8px 0; font-weight: 700; color: #16a34a; text-align: right;">${current_price}</td>
                        </tr>
                    </table>
                </div>
                {"<p style='color: #475569; font-size: 14px;'><strong>Note:</strong> " + note + "</p>" if note else ""}
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
                <p style="color: #94a3b8; font-size: 12px; margin-bottom: 0;">
                    This is an automated notification from Investor Hub.
                </p>
            </div>
        </body>
        </html>
        """

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from_email or settings.smtp_user
            msg["To"] = to_email

            # Plain text fallback
            text_body = (
                f"Price Alert Triggered: {stock_symbol}\n\n"
                f"Alert Type: {alert_type} (price {direction} target)\n"
                f"Target Price: ${target_price}\n"
                f"Current Price: ${current_price}\n"
                f"{'Note: ' + note if note else ''}\n"
            )

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            if settings.smtp_use_tls:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)

            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"Alert email sent to {to_email} for {stock_symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert email to {to_email}: {e}")
            return False
