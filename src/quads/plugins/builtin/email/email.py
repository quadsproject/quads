from quads.plugins.interfaces.email import EmailPlugin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from smtplib import SMTP, SMTPException
import markdown
import os
from jinja2 import Environment, FileSystemLoader
from typing import List, Optional, Dict


class EmailPlugin(EmailPlugin):
    """
    Email plugin implementing EmailPlugin interface.

    Also implements NotifierPlugin for backward compatibility.
    """

    name = "email"
    version = "1.0.0"
    description = "Send notifications via email with HTML support"
    author = "QUADS Team"

    def initialize(self) -> bool:
        self.smtp_host = self.config.get("smtp_host")
        self.smtp_port = self.config.get("smtp_port", 25)
        self.from_address = self.config.get("from_address")
        self.templates_path = self.config.get("templates_path", "/opt/quads/templates")

        if not self.smtp_host:
            self.logger.error("smtp_host not configured")
            return False
        if not self.from_address:
            self.logger.error("from_address not configured")
            return False

        # Initialize Jinja2 environment for templates
        if os.path.exists(self.templates_path):
            self.jinja_env = Environment(loader=FileSystemLoader(self.templates_path))
        else:
            self.logger.warning(f"Templates path {self.templates_path} does not exist")
            self.jinja_env = None

        return True

    def shutdown(self) -> None:
        pass

    def health_check(self) -> bool:
        try:
            with SMTP(self.smtp_host, self.smtp_port) as s:
                s.noop()
            return True
        except SMTPException:
            return False

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
        """Send email with full mail-specific features"""
        try:
            # Create message container
            if attachments or not html:
                msg = MIMEMultipart()
            else:
                msg = MIMEMultipart("alternative")

            # Set headers
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = ", ".join(recipients)

            if cc:
                msg["Cc"] = ", ".join(cc)
            if reply_to:
                msg["Reply-To"] = reply_to

            # Add custom headers from kwargs
            custom_headers = kwargs.get("headers", {})
            for header_name, header_value in custom_headers.items():
                msg[header_name] = header_value

            # Prepare body
            if html:
                # Convert markdown to HTML
                html_body = markdown.markdown(body, extensions=["tables", "fenced_code", "nl2br"])
                msg.attach(MIMEText(html_body, "html"))
            else:
                # Plain text
                msg.attach(MIMEText(body, "plain"))

            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment["content"])
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {attachment['filename']}",
                    )
                    msg.attach(part)

            # Send email
            all_recipients = recipients[:]
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            with SMTP(self.smtp_host, self.smtp_port) as s:
                s.send_message(msg, to_addrs=all_recipients)

            self.logger.info(f"Email sent to {len(all_recipients)} recipients: {subject}")
            return True

        except SMTPException as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending email: {e}")
            return False

    async def send_template_mail(
        self,
        template_name: str,
        recipients: List[str],
        template_vars: Dict,
        **kwargs,
    ) -> bool:
        """Send email using a Jinja2 template"""
        if not self.jinja_env:
            self.logger.error("Template environment not initialized")
            return False

        try:
            # Load template
            template = self.jinja_env.get_template(template_name)

            # Render body
            body = template.render(**template_vars)

            # Extract subject from template vars or use template name
            subject = template_vars.get("subject", f"Notification: {template_name}")

            # Send using send_mail
            return await self.send_mail(
                subject=subject,
                body=body,
                recipients=recipients,
                **kwargs,
            )

        except Exception as e:
            self.logger.error(f"Failed to send template email: {e}")
            return False

    # Backward compatibility with old NotifierPlugin interface
    async def send_notification(self, subject: str, message: str, recipients: List[str], **kwargs) -> bool:
        """Backward compatibility method - delegates to send_mail()"""
        return await self.send_mail(
            subject=subject,
            body=message,
            recipients=recipients,
            html=True,
            **kwargs,
        )
