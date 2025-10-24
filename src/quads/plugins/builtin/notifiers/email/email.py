from quads.plugins.interfaces.notifier import NotifierPlugin
from email.mime.text import MIMEText
from smtplib import SMTP, SMTPException
import markdown
from typing import List


class EmailNotifierPlugin(NotifierPlugin):
    name = "email_notifier"
    version = "1.0.0"
    description = "Send notifications via email"
    author = "QUADS Team"

    def initialize(self) -> bool:
        self.smtp_host = self.config.get("smtp_host")
        self.from_address = self.config.get("from_address")
        if not self.smtp_host:
            self.logger.error("smtp_host not configured")
            return False
        return True

    def shutdown(self) -> None:
        pass

    def health_check(self) -> bool:
        try:
            with SMTP(self.smtp_host) as s:
                s.noop()
            return True
        except SMTPException:
            return False

    async def send_notification(self, subject: str, message: str, recipients: List[str], **kwargs) -> bool:
        msg = MIMEText(markdown.markdown(message, extensions=["tables"]), "html")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(recipients)

        try:
            with SMTP(self.smtp_host) as s:
                s.send_message(msg)
            return True
        except SMTPException as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
