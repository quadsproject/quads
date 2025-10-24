import asyncio
import ssl
from typing import List, Optional
from quads.plugins.interfaces.chat import ChatPlugin


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
        self.use_ssl = self.config.get("ssl", False)
        self.nickname = self.config.get("nickname", "quads-bot")
        self.username = self.config.get("username", "quads")
        self.realname = self.config.get("realname", "QUADS Notification Bot")
        self.password = self.config.get("password")
        self.nickserv_password = self.config.get("nickserv_password")
        self.default_channel = self.config.get("default_channel", "#quads")
        self.timeout = self.config.get("timeout", 30)

        if not self.server:
            self.logger.error("server not configured for IRC notifier")
            return False

        self.logger.info(
            f"IRC notifier initialized (server: {self.server}:{self.port}, " f"channel: {self.default_channel})"
        )
        return True

    async def send_message(
        self,
        title: str,
        text: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        """
        Send message to IRC channels.

        Args:
            title: Message title/header
            text: Message body
            channels: List of IRC channels (e.g., ["#cloud-ops", "#alerts"])
        """
        target_channels = channels if channels else [self.default_channel]

        # Format message with title
        formatted_message = f"[{title}] {text}" if title else text

        return await self._send_to_channels(target_channels, formatted_message)

    async def _send_to_channels(self, channels: List[str], messages: List[str]) -> bool:
        """Connect to IRC and send messages to specified channels"""
        reader = None
        writer = None

        try:
            # Establish connection
            if self.use_ssl:
                ssl_context = ssl.create_default_context()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.server, self.port, ssl=ssl_context),
                    timeout=self.timeout,
                )
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.server, self.port),
                    timeout=self.timeout,
                )

            # Send server password if configured
            if self.password:
                await self._send_raw(writer, f"PASS {self.password}")

            # Register with the server
            await self._send_raw(writer, f"NICK {self.nickname}")
            await self._send_raw(writer, f"USER {self.username} 0 * :{self.realname}")

            # Wait for welcome message (001) or error
            if not await self._wait_for_registration(reader, writer):
                self.logger.error("Failed to register with IRC server")
                return False

            # Identify with NickServ if configured
            if self.nickserv_password:
                await self._send_raw(writer, f"PRIVMSG NickServ :IDENTIFY {self.nickserv_password}")
                await asyncio.sleep(1)  # Give NickServ time to process

            # Join channels and send messages
            for channel in channels:
                # Ensure channel starts with #
                if not channel.startswith("#"):
                    channel = f"#{channel}"

                await self._send_raw(writer, f"JOIN {channel}")
                await asyncio.sleep(0.5)  # Brief delay after joining

                for msg in messages:
                    if msg.strip():  # Don't send empty messages
                        await self._send_raw(writer, f"PRIVMSG {channel} :{msg}")
                        await asyncio.sleep(0.2)  # Rate limiting

                await self._send_raw(writer, f"PART {channel}")

            # Quit gracefully
            await self._send_raw(writer, "QUIT :QUADS notification complete")

            self.logger.debug(f"IRC messages sent to {channels}")
            return True

        except asyncio.TimeoutError:
            self.logger.error(f"IRC connection to {self.server}:{self.port} timed out")
            return False
        except ConnectionRefusedError:
            self.logger.error(f"IRC connection to {self.server}:{self.port} refused")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send IRC notification: {e}")
            return False
        finally:
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _send_raw(self, writer: asyncio.StreamWriter, message: str) -> None:
        """Send a raw IRC command"""
        writer.write(f"{message}\r\n".encode("utf-8"))
        await writer.drain()
        self.logger.debug(f"IRC >> {message}")

    async def _wait_for_registration(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        """
        Wait for successful registration with the IRC server.

        Handles PING/PONG during registration and looks for the 001 welcome message.
        """
        try:
            deadline = asyncio.get_event_loop().time() + self.timeout

            while asyncio.get_event_loop().time() < deadline:
                try:
                    line = await asyncio.wait_for(
                        reader.readline(),
                        timeout=deadline - asyncio.get_event_loop().time(),
                    )
                except asyncio.TimeoutError:
                    return False

                if not line:
                    return False

                decoded = line.decode("utf-8", errors="replace").strip()
                self.logger.debug(f"IRC << {decoded}")

                # Handle PING during registration
                if decoded.startswith("PING"):
                    pong_param = decoded.split(" ", 1)[1] if " " in decoded else ""
                    await self._send_raw(writer, f"PONG {pong_param}")
                    continue

                # Parse numeric replies
                parts = decoded.split(" ")
                if len(parts) >= 2:
                    # Check for 001 (RPL_WELCOME) - successful registration
                    if parts[1] == "001":
                        return True
                    # Check for error numerics
                    if parts[1] in ("431", "432", "433", "436", "437", "451", "462"):
                        self.logger.error(f"IRC registration error: {decoded}")
                        return False

            return False

        except Exception as e:
            self.logger.error(f"Error during IRC registration: {e}")
            return False
