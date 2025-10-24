from src.quads.plugins.interfaces.validator import ValidatorPlugin
from src.quads.config import Config


class EnvironmentValidatorPlugin(ValidatorPlugin):
    """Environment validator plugin"""

    def __init__(self):
        self.environment = Config.environment

    def validate(self) -> bool:
        """Validate the environment"""
        pass
