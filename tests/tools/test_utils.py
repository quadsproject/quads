"""Tests for quads.helpers.utils"""

from unittest.mock import MagicMock

from quads.helpers.utils import is_libvirt


class TestIsLibvirt:
    def _host(self, model):
        h = MagicMock()
        h.model = model
        return h

    def test_libvirt_uppercase(self):
        assert is_libvirt(self._host("LIBVIRT")) is True

    def test_libvirt_lowercase(self):
        assert is_libvirt(self._host("libvirt")) is True

    def test_libvirt_mixed_case(self):
        assert is_libvirt(self._host("Libvirt")) is True

    def test_non_libvirt_dell(self):
        assert is_libvirt(self._host("Dell")) is False

    def test_non_libvirt_supermicro(self):
        assert is_libvirt(self._host("6049P")) is False
