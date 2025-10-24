# src/quads/plugins/interfaces/mail_notifier.py
"""
Mail Notifier Interface - For email-based notifications

Email notifications support:
- HTML formatting with markdown conversion
- Formal email structure (Subject, From, To, CC, BCC)
- Attachments
- Plain text fallback
- Email threading via headers
"""
from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List, Optional, Dict


class MailNotifierPlugin(BasePlugin):
    """Interface for email notification plugins"""

    @abstractmethod
    async def send_mail(
        self,
        subject: str,
        body: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        html: bool = True,
        **kwargs,
    ) -> bool:
        """
        Send an email notification.

        Args:
            subject: Email subject line
            body: Email body (can be markdown if html=True)
            recipients: List of recipient email addresses
            cc: Optional list of CC email addresses
            bcc: Optional list of BCC email addresses
            reply_to: Optional reply-to address
            attachments: Optional list of attachments [{"filename": str, "content": bytes, "content_type": str}]
            html: If True, convert markdown body to HTML; if False, send plain text
            **kwargs: Additional email-specific parameters (headers, priority, etc.)

        Returns:
            bool: True if email sent successfully, False otherwise

        Example:
            await mail_notifier.send_mail(
                subject="Cloud Assignment Ending",
                body="Your cloud **cloud01** will expire in 3 days.\n\n## Details\n...",
                recipients=["user@example.com"],
                cc=["manager@example.com"],
                html=True
            )
        """
        pass

    @abstractmethod
    async def send_template_mail(
        self,
        template_name: str,
        recipients: List[str],
        template_vars: Dict,
        **kwargs,
    ) -> bool:
        """
        Send an email using a template.

        Args:
            template_name: Name of the email template to use
            recipients: List of recipient email addresses
            template_vars: Dictionary of variables to render in template
            **kwargs: Additional email-specific parameters

        Returns:
            bool: True if email sent successfully, False otherwise

        Example:
            await mail_notifier.send_template_mail(
                template_name="cloud_expiring",
                recipients=["user@example.com"],
                template_vars={"cloud": "cloud01", "days": 3, "owner": "user"}
            )
        """
        pass
