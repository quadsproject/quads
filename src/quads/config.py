#!/usr/bin/env python3
import logging
import os

import yaml

logger = logging.getLogger(__name__)

# Allow overriding config directory for development (e.g. QUADS_CONF_DIR=/path/to/repo/conf)
QUADS_CONF_DIR = os.environ.get("QUADS_CONF_DIR", "/opt/quads/conf")
DEFAULT_CONF_PATH = os.path.join(QUADS_CONF_DIR, "quads.yml")
WEB_CONF_PATH = os.path.join(QUADS_CONF_DIR, "quadsweb.yml")
SS_CONF_PATH = os.path.join(QUADS_CONF_DIR, "selfservice.yml")
PLUGINS_CONF_PATH = os.path.join(QUADS_CONF_DIR, "plugins.yml")
OAUTH_CONF_PATH = os.path.join(QUADS_CONF_DIR, "oauth.yml")


class _ConfigBase:
    def __init__(self):
        self.loaded = False
        self.load_from_yaml(DEFAULT_CONF_PATH)
        self.load_from_yaml(WEB_CONF_PATH)
        self.load_from_yaml(SS_CONF_PATH)
        self.load_from_yaml(PLUGINS_CONF_PATH)
        self.load_from_yaml(OAUTH_CONF_PATH)

    def load_from_yaml(self, filepath: str = DEFAULT_CONF_PATH):
        """
        Load values from yaml file as attributes of this class.
        Will never override existing attributes.
        Skips missing files (e.g. optional configs or dev without full install).
        """
        if not os.path.isfile(filepath):
            logger.debug("Config file not found, skipping: %s", filepath)
            return
        with open(filepath, "r") as config_file:
            conf = yaml.safe_load(config_file)
            assert type(conf) is dict

            for key, value in conf.items():
                if hasattr(self, key):
                    logger.debug(f"Key '{key}' is already defined on config class, not overriding")
                    continue
                setattr(self, key, value)

            logger.debug(f"Loaded yaml config from '{filepath}'")
            self.loaded = True

    def __getitem__(self, item: str):
        """
        Allow acces thru subscription:

        Config['key'] === Config.key
        Config['QUADS_VERSION'] === Config.QUADS_VERSION

        This should eventually be removed, having two
        ways to access one thing does not sound safe.
        """
        try:
            return getattr(self, item)
        except AttributeError as attr_exc:
            raise KeyError() from attr_exc

    def get(self, key: str, default=None):
        """
        Args:
            key: Key that we want the value for.
            default: Value that is returned in case the key is not present. (Optional, it defaults to None)

        Returns: Value for key from the config, if key isn't present value specified in "default" argument is returned.
        """
        return getattr(self, key, default)


class _Config(_ConfigBase):
    """
    Configuration "singleton"

    Class defined values should be considered globals (capitalized)
    and they always override values set in yaml.

    Examples:
        Config.QUADS_VERSION
        Config.email_host
    """

    LOGFMT = "%(asctime)-12s : %(levelname)-8s - %(message)s"
    STDFMT = "- %(levelname)-8s - %(message)s"

    API = "v3"

    @property
    def API_URL(self):
        return os.path.join(self.quads_base_url, "api", self.API)

    FPING_TIMEOUT = 10000

    QUADSVERSION = "2.2.6"
    QUADSCODENAME = "maximilian"

    # Model/name fragments for Supermicro hosts that skip Badfish and use ipmitool.
    # Extend via plugins.badfish.skip_for_supermicro_models in plugins.yml.
    SUPERMICRO: list = []

    def __init__(self):
        self.SUPERMICRO = list(self.__class__.SUPERMICRO)
        super().__init__()
        self._apply_yaml_extensions()

    def _apply_yaml_extensions(self):
        badfish_cfg = getattr(self, "plugins", {}).get("badfish", {})
        raw = badfish_cfg.get("skip_for_supermicro_models")
        if raw is None:
            # backward compat: accept old key name with a deprecation notice
            raw = badfish_cfg.get("supported_supermicro")
            if raw is not None:
                logger.warning(
                    "plugins.badfish.supported_supermicro is deprecated; "
                    "rename to skip_for_supermicro_models in plugins.yml"
                )
        if raw is None:
            return
        if not raw:
            logger.debug("Skipping empty skip_for_supermicro_models in plugins.badfish")
            return
        existing_lower = {m.lower() for m in self.SUPERMICRO}
        for model in [m.strip() for m in str(raw).split(",") if m.strip()]:
            if model.lower() not in existing_lower:
                self.SUPERMICRO.append(model)
                existing_lower.add(model.lower())
        logger.debug("Extended SUPERMICRO from plugins.badfish.skip_for_supermicro_models")

    OFFSETS = {"em1": 0, "em2": 1, "em3": 2, "em4": 3, "em5": 4}
    TEMPLATES_PATH = os.environ.get(
        "QUADS_TEMPLATES_PATH",
        (
            "/opt/quads/templates"
            if os.path.isdir("/opt/quads/templates")
            else os.path.join(os.path.dirname(__file__), "templates")
        ),
    )
    INTERFACES = {
        "em1": ["172.16", "172.21"],
        "em2": ["172.17", "172.22"],
        "em3": ["172.18", "172.23"],
        "em4": ["172.19", "172.24"],
        "em5": ["172.20", "172.25"],
    }


# Making sure there is exactly one instance of config used elsewhere
Config = _Config()

if __name__ == "__main__":
    if not Config.loaded:
        Config.load_from_yaml(DEFAULT_CONF_PATH)
        Config.load_from_yaml(WEB_CONF_PATH)
        Config.load_from_yaml(SS_CONF_PATH)
        Config.load_from_yaml(PLUGINS_CONF_PATH)
