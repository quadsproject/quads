from datetime import datetime

from tests.cli.test_base import TestBase


class TestSummary(TestBase):
    def test_summary_all_detail(self, capsys):
        self.cli_args["all"] = True
        self.cli_args["detail"] = True
        self.quads_cli_call("summary")
        output = capsys.readouterr().out
        assert "Cloud Summary" in output
        assert "cloud01" in output
        assert "Spare Pool" in output
        assert "cloud04" in output
        assert "cloud99" in output

    def test_summary(self, capsys):
        self.cli_args["all"] = False
        self.cli_args["detail"] = False
        self.quads_cli_call("summary")
        output = capsys.readouterr().out
        assert "Cloud Summary" in output
        assert "cloud99" in output

    def test_summary_date(self, capsys):
        today = datetime.now().strftime("%Y-%m-%d %H:%M")

        self.cli_args["datearg"] = today
        self.cli_args["all"] = False
        self.cli_args["detail"] = False
        self.quads_cli_call("summary")
        output = capsys.readouterr().out
        assert "Cloud Summary" in output
        assert "cloud99" in output
