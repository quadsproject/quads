#!/usr/bin/env python3

import logging
import markdown
from smtplib import SMTPException, SMTP

from email.message import EmailMessage
from email.mime.text import MIMEText
from quads.config import Config

logger = logging.getLogger(__name__)


class Postman(object):
    def __init__(self, subject, to, cc, content):
        self.subject = subject
        self.to = to
        self.cc = cc
        self.content = content

    def compose(self):
        self.reply_to = "dev-null@%s" % Config["domain"]
        self.user_agent = Config["mail_user_agent"]
        self.from_address = "%s <%s>" % (
            Config["mail_display_name"],
            "@".join(["quads", Config["domain"]]),
        )
        msg = MIMEText(markdown.markdown(self.content, extensions=['tables']), "html")
        msg["Subject"] = self.subject
        msg["From"] = self.from_address
        msg["To"] = "@".join([self.to, Config["domain"]])
        msg["Cc"] = ",".join(self.cc)
        msg.add_header("Reply-To", self.reply_to)
        msg.add_header("User-Agent", self.user_agent)

        return msg

    def send_email(self):
        msg = self.compose()
        email_host = Config["email_host"]
        with SMTP(email_host) as s:
            try:
                logger.debug(msg)
                s.send_message(msg)
            except SMTPException as ex:
                logger.debug(ex)
                logger.error("Postman got bit by a dog, woof! woof!")
                return False
        return True
