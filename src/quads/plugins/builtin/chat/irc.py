from typing import List, Optional
from quads.plugins.interfaces.chat import ChatPlugin
from quads.tools.external.netcat import Netcat


class IRCPlugin(ChatPlugin):
    """
    IRC notifier plugin implementing ChatPlugin interface.

    Connects to IRC servers and sends messages to channels.
    """

    name = "irc"
    version = "1.0.0"
    description = "Send notifications to IRC channels"
    author = "QUADS Team"

    def initialize(self) -> bool:
        """Initialize IRC connection settings"""
        self.server = self.config.get("server")
        self.port = self.config.get("port", 6667)
        self.default_channel = self.config.get("default_channel", "#quads")

        if not self.server:
            self.logger.error("server not configured for IRC notifier")
            return False

        self.logger.info(
            f"IRC notifier initialized (server: {self.server}:{self.port}, " f"channel: {self.default_channel})"
        )
        return True

    async def send_message(
        self,
        message: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        try:
            target_channels = channels if channels else [self.default_channel]
            for channel in target_channels:
                async with Netcat(self.server, self.port) as nc:
                    message = f"{channel} {message}"
                    await nc.write(bytes(message.encode("utf-8")))
            return True
        except (TypeError, BrokenPipeError) as ex:
            self.logger.debug(ex)
            self.logger.error("Beep boop netcat can't communicate with your IRC.")
            return False
