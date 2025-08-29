import smtplib
from unittest.mock import patch

from quads.config import Config
from quads.tools.external.postman import Postman


class TestPostman:
    @patch("quads.tools.external.postman.SMTP")
    def test_email_sent_successfully(self, mocked_smtp):
        postman = Postman("Test Subject", "test", [], "Test Content")
        assert postman.send_email() == True

    @patch("quads.tools.external.postman.SMTP")
    def test_email_sent_with_correct_details(self, mocked_smtp):
        postman = Postman(
            "Test Subject",
            "test",
            ["cc1@example.com", "cc2@example.com"],
            "Test Content",
        )
        postman.send_email()
        assert postman.subject == "Test Subject"
        assert postman.to == "test"
        assert postman.cc == ["cc1@example.com", "cc2@example.com"]
        assert postman.content == "Test Content"

    @patch("quads.tools.external.postman.SMTP")
    def test_empty_subject_to_cc_content(self, mocked_smtp):
        postman = Postman("", "", [], "")
        assert postman.send_email() is True

    @patch("quads.tools.external.postman.SMTP")
    def test_smtp_exception_raised(self, mocked_smtp):
        mocked_smtp.return_value.__enter__.return_value.send_message.side_effect = smtplib.SMTPException
        postman = Postman("Test Subject", "test", [], "Test Content")
        assert postman.send_email() is False

    @patch("quads.tools.external.postman.SMTP")
    @patch.object(
        Config,
        "domain",
        "test.com",
    )
    def test_email_sent_with_correct_reply_to(self, mocked_smtp):
        postman = Postman("Test Subject", "test", [], "Test Content")
        postman.send_email()
        assert postman.reply_to == "dev-null@test.com"

    @patch("quads.tools.external.postman.SMTP")
    @patch.object(
        Config,
        "mail_user_agent",
        "Test User Agent",
    )
    def test_email_sent_with_correct_user_agent(self, mocked_smtp):
        postman = Postman("Test Subject", "test", [], "Test Content")
        postman.send_email()
        assert postman.user_agent == "Test User Agent"

    @patch("quads.tools.external.postman.SMTP")
    def test_postman_instance_created_with_no_cc(self, mocked_smtp):
        postman = Postman("Test Subject", "test", None, "Test Content")
        assert postman.cc is None

    @patch("quads.tools.external.postman.SMTP")
    def test_compose_and_send_email_successfully(self, mocked_smtp):
        postman = Postman("Test Subject", "test", [], "Test Content")
        assert postman.send_email() is True

    def test_compose_email_with_only_required_fields(self):
        postman = Postman("Test Subject", "test", [], "Test Content")
        msg = postman.compose()
        assert msg["Subject"] == "Test Subject"
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "test@example.com"
        assert msg["Cc"] == ""

    def test_compose_email_with_all_fields(self):
        postman = Postman(
            "Test Subject",
            "test",
            ["cc1@example.com", "cc2@example.com"],
            "Test Content",
        )
        msg = postman.compose()
        assert msg["Subject"] == "Test Subject"
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "test@example.com"
        assert msg["Cc"] == "cc1@example.com,cc2@example.com"

    def test_compose_email_with_empty_subject(self):
        postman = Postman("", "test", [], "Test Content")
        msg = postman.compose()
        assert msg["Subject"] == ""
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "test@example.com"
        assert msg["Cc"] == ""

    def test_compose_email_with_empty_content(self):
        postman = Postman("Test Subject", "test", [], "")
        msg = postman.compose()
        assert msg["Subject"] == "Test Subject"
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "test@example.com"
        assert msg["Cc"] == ""

    def test_compose_email_with_empty_to_and_cc_fields(self):
        postman = Postman("Test Subject", "", [], "Test Content")
        msg = postman.compose()
        assert msg["Subject"] == "Test Subject"
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "@example.com"
        assert msg["Cc"] == ""

    def test_compose_email_with_long_subject_and_content(self):
        subject = "a" * 1000
        content = "b" * 10000
        postman = Postman(subject, "test", [], content)
        msg = postman.compose()
        assert msg["Subject"] == subject
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "test@example.com"
        assert msg["Cc"] == ""

    def test_compose_email_with_non_ASCII_characters(self):
        subject = "助けて"
        content = "助けて"
        postman = Postman(subject, "test", [], content)
        msg = postman.compose()
        assert msg["Subject"] == subject
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "test@example.com"
        assert msg["Cc"] == ""

    def test_compose_email_with_multiple_recipients(self):
        postman = Postman(
            "Test Subject",
            "test1",
            ["test2@example.com", "test3@example.com"],
            "Test Content",
        )
        msg = postman.compose()
        assert msg["Subject"] == "Test Subject"
        assert msg["From"] == "QUADS Scheduler <quads@example.com>"
        assert msg["To"] == "test1@example.com"
        assert msg["Cc"] == "test2@example.com,test3@example.com"
