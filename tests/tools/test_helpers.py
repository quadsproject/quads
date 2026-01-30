import unittest
import asyncio
from unittest.mock import patch, MagicMock
from quads.tools import helpers


class TestQuadsHelpers(unittest.TestCase):

    def setUp(self):
        self.mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        self.mock_loop.is_closed.return_value = False

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_get_or_create_loop_exists_and_running(self, mock_get, mock_new, mock_set):
        """Test that if a valid loop exists, it is returned and no new loop is created."""
        mock_get.return_value = self.mock_loop

        result = helpers.get_or_create_event_loop()

        self.assertEqual(result, self.mock_loop)
        mock_get.assert_called_once()
        mock_new.assert_not_called()
        mock_set.assert_not_called()

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_get_or_create_loop_exists_but_closed(self, mock_get, mock_new, mock_set):
        """Test that if a loop exists but is closed, a new one is created."""
        # Arrange
        mock_get.return_value = self.mock_loop
        self.mock_loop.is_closed.return_value = True

        new_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        mock_new.return_value = new_loop

        # Act
        result = helpers.get_or_create_event_loop()

        # Assert
        self.assertEqual(result, new_loop)
        mock_get.assert_called_once()
        mock_new.assert_called_once()
        mock_set.assert_called_once_with(new_loop)

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.get_event_loop")
    def test_get_or_create_loop_missing(self, mock_get, mock_new, mock_set):
        """Test that if get_event_loop raises RuntimeError, a new loop is created/set."""
        mock_get.side_effect = RuntimeError("No event loop")
        mock_new.return_value = self.mock_loop

        result = helpers.get_or_create_event_loop()

        self.assertEqual(result, self.mock_loop)
        mock_get.assert_called_once()
        mock_new.assert_called_once()
        mock_set.assert_called_once_with(self.mock_loop)

    def test_strtobool(self):
        """Basic coverage for strtobool."""
        # True cases
        self.assertTrue(helpers.strtobool("y"))
        self.assertTrue(helpers.strtobool("YES"))
        self.assertTrue(helpers.strtobool("True"))
        self.assertTrue(helpers.strtobool("1"))
        self.assertTrue(helpers.strtobool("on"))

        # Non-string True cases
        self.assertTrue(helpers.strtobool(True))
        self.assertTrue(helpers.strtobool(1))

        # False cases
        self.assertFalse(helpers.strtobool("n"))
        self.assertFalse(helpers.strtobool("NO"))
        self.assertFalse(helpers.strtobool("False"))
        self.assertFalse(helpers.strtobool("0"))

        # Non-string False cases
        self.assertFalse(helpers.strtobool(False))
        self.assertFalse(helpers.strtobool(0))
