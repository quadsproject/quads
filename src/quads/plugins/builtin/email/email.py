from quads.plugins.interfaces.email import EmailPlugin
from quads.plugins.manager import PluginManager
from email.mime.text import MIMEText
from smtplib import SMTP, SMTPException
import markdown
from typing import List, Optional


class EmailPlugin(EmailPlugin):
    """
    Email plugin implementing EmailPlugin interface.

    Also implements NotifierPlugin for backward compatibility.
    """

    name = "email"
    version = "1.0.0"
    description = "Send notifications via email with HTML support"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None) -> bool:
        self.mail_display_name = self.config.get("mail_display_name")
        self.smtp_host = self.config.get("smtp_host")
        self.smtp_port = self.config.get("smtp_port", 25)
        self.from_address = self.config.get("from_address")
        self.reply_to = self.config.get("reply_to")
        self.user_agent = self.config.get("user_agent")

        if not self.smtp_host:
            self.logger.error("smtp_host not configured")
            return False
        if not self.from_address:
            self.logger.error("from_address not configured")
            return False

        return True

    def compose(self, content: str, subject: str, recipients: List[str], cc: Optional[List[str]] = None):
        msg = MIMEText(markdown.markdown(content, extensions=["tables"]), "html")
        msg["Subject"] = subject
        msg["From"] = f"{self.mail_display_name} <{self.from_address}>"
        msg["To"] = "@".join(recipients)
        msg["Cc"] = ",".join(cc)
        msg.add_header("Reply-To", self.reply_to)
        msg.add_header("User-Agent", self.user_agent)

        return msg

    async def send_mail(
        self,
        subject: str,
        content: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        try:
            msg = self.compose(content, subject, recipients, cc)
            with SMTP(self.smtp_host, self.smtp_port) as s:
                s.send_message(msg, to_addrs=recipients)

            self.logger.info(f"Email sent to {len(recipients)} recipients: {subject}")
            return True

        except SMTPException as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending email: {e}")
            return False
