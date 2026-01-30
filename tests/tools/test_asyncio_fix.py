import unittest
import sys
import importlib
import asyncio
from unittest.mock import patch, MagicMock


class TestQuadsAsyncioFixes(unittest.TestCase):

    def setUp(self):
        self.mock_loop = MagicMock()
        self.mock_loop.run_until_complete.return_value = None

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def check_asyncio_fix(
        self, module_path, function_name=None, class_name=None, mock_get=None, mock_new=None, mock_set=None
    ):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        if module_path in sys.modules:
            del sys.modules[module_path]

        module = importlib.import_module(module_path)
        importlib.reload(module)

        if class_name:
            cls = getattr(module, class_name)
            try:
                cls()
            except TypeError:
                try:
                    cls(MagicMock())
                except TypeError:
                    pass

        if function_name:
            if hasattr(module, function_name):
                func = getattr(module, function_name)
                try:
                    func()
                except Exception:
                    pass

        return mock_get, mock_new, mock_set

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_tools_helpers(self, mock_get, mock_new, mock_set):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        import quads.tools.helpers

        importlib.reload(quads.tools.helpers)

        mock_get.assert_called()
        mock_new.assert_called()
        mock_set.assert_called_with(self.mock_loop)

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_tools_notify_tenant(self, mock_get, mock_new, mock_set):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        import quads.tools.notify_tenant

        importlib.reload(quads.tools.notify_tenant)

        if hasattr(quads.tools.notify_tenant, "main"):
            try:
                quads.tools.notify_tenant.main()
            except Exception:
                pass

        mock_get.assert_called()
        mock_new.assert_called()
        mock_set.assert_called_with(self.mock_loop)

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_tools_foreman_heal(self, mock_get, mock_new, mock_set):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        import quads.tools.foreman_heal

        importlib.reload(quads.tools.foreman_heal)

        if hasattr(quads.tools.foreman_heal, "main"):
            try:
                quads.tools.foreman_heal.main()
            except Exception:
                pass

        mock_get.assert_called()
        mock_new.assert_called()
        mock_set.assert_called_with(self.mock_loop)

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_tools_jira_workflow(self, mock_get, mock_new, mock_set):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        import quads.tools.jira_workflow

        importlib.reload(quads.tools.jira_workflow)

        if hasattr(quads.tools.jira_workflow, "main"):
            try:
                quads.tools.jira_workflow.main()
            except Exception:
                pass

        mock_get.assert_called()
        mock_new.assert_called()
        mock_set.assert_called_with(self.mock_loop)

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_tools_jira_watchers(self, mock_get, mock_new, mock_set):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        import quads.tools.jira_watchers

        importlib.reload(quads.tools.jira_watchers)

        if hasattr(quads.tools.jira_watchers, "main"):
            try:
                quads.tools.jira_watchers.main()
            except Exception:
                pass

        mock_get.assert_called()
        mock_new.assert_called()
        mock_set.assert_called_with(self.mock_loop)

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_external_badfish(self, mock_get, mock_new, mock_set):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        import quads.tools.external.badfish

        importlib.reload(quads.tools.external.badfish)

        try:
            quads.tools.external.badfish.Badfish("host", "user", "pass", MagicMock(), 3)
        except Exception:
            pass

        mock_get.assert_called()
        mock_new.assert_called()
        mock_set.assert_called_with(self.mock_loop)

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_cli_cli(self, mock_get, mock_new, mock_set):
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        import quads.cli.cli

        importlib.reload(quads.cli.cli)

        if hasattr(quads.cli.cli, "main"):
            try:
                quads.cli.cli.main()
            except Exception:
                pass

        self.assertTrue(mock_new.call_count >= 1)
        self.assertTrue(mock_set.call_count >= 1)
