import logging
import os.path
import unittest
from unittest.mock import patch

from quads.config import _ConfigBase, _Config  # noqa
from quads.helpers.utils import is_supermicro


def get_mock_config():
    class Config(_ConfigBase):
        KEY = "value"

    return Config()


def _make_config_with_badfish(badfish_cfg):
    """Instantiate _Config without file I/O, inject plugins.badfish, apply extensions."""
    cfg = _Config.__new__(_Config)
    cfg.SUPERMICRO = []
    cfg.plugins = {"badfish": badfish_cfg}
    cfg._apply_yaml_extensions()
    return cfg


# noinspection PyUnresolvedReferences
class TestConfig(unittest.TestCase):
    def test_getattr(self):
        conf = get_mock_config()
        self.assertEqual(conf.KEY, "value")

        with self.assertRaises(AttributeError):
            _ = conf.NOT_EXISTS

    def test_getitem(self):
        conf = get_mock_config()
        self.assertEqual(conf["KEY"], "value")

        with self.assertRaises(KeyError):
            _ = conf["not_exists"]

    def test_load_yaml(self):
        test_yaml_path = os.path.join(os.path.dirname(__file__), "fixtures/test_conf.yaml")
        assert os.path.exists(test_yaml_path), f"Missing test fixture: {test_yaml_path}"

        conf = get_mock_config()
        conf.load_from_yaml(test_yaml_path)

        # Both in yaml and on class, class attr should not be overridden
        self.assertEqual(conf.KEY, "value")

        self.assertDictEqual(
            conf.test,
            {"gateway": "10.12.81.254", "iprange": "10.12.80.0/23", "vlanid": 601},
        )


class TestConfigExtensions(unittest.TestCase):
    def test_skip_for_supermicro_models_populates_list(self):
        cfg = _make_config_with_badfish({"skip_for_supermicro_models": "6029p, 1028r"})
        self.assertIn("6029p", cfg.SUPERMICRO)
        self.assertIn("1028r", cfg.SUPERMICRO)
        self.assertEqual(len(cfg.SUPERMICRO), 2)

    def test_deprecated_key_warns_and_populates(self):
        with self.assertLogs("quads.config", level="WARNING") as log:
            cfg = _make_config_with_badfish({"supported_supermicro": "6029p"})
        self.assertIn("6029p", cfg.SUPERMICRO)
        self.assertTrue(any("deprecated" in msg for msg in log.output))

    def test_missing_key_leaves_list_empty(self):
        cfg = _make_config_with_badfish({})
        self.assertEqual(cfg.SUPERMICRO, [])

    def test_deduplication_is_case_insensitive(self):
        cfg = _make_config_with_badfish({"skip_for_supermicro_models": "6029P, 6029p"})
        self.assertEqual(len(cfg.SUPERMICRO), 1)

    def test_new_key_takes_precedence_over_deprecated(self):
        cfg = _make_config_with_badfish({
            "skip_for_supermicro_models": "6029p",
            "supported_supermicro": "1028r",
        })
        self.assertIn("6029p", cfg.SUPERMICRO)
        self.assertNotIn("1028r", cfg.SUPERMICRO)


class TestIsSupermicro(unittest.TestCase):
    def test_matching_hostname_returns_true(self):
        with patch("quads.helpers.utils.Config") as mock_cfg:
            mock_cfg.SUPERMICRO = ["6029p"]
            self.assertTrue(is_supermicro("sm-6029p-01.example.com"))

    def test_non_matching_hostname_returns_false(self):
        with patch("quads.helpers.utils.Config") as mock_cfg:
            mock_cfg.SUPERMICRO = ["6029p"]
            self.assertFalse(is_supermicro("dell-r640-01.example.com"))

    def test_empty_supermicro_list_returns_false(self):
        with patch("quads.helpers.utils.Config") as mock_cfg:
            mock_cfg.SUPERMICRO = []
            self.assertFalse(is_supermicro("sm-6029p-01.example.com"))

    def test_match_is_case_insensitive(self):
        with patch("quads.helpers.utils.Config") as mock_cfg:
            mock_cfg.SUPERMICRO = ["6029P"]
            self.assertTrue(is_supermicro("sm-6029p-01.example.com"))


if __name__ == "__main__":
    unittest.main()
