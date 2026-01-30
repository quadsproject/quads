#!/usr/bin/env python3
import socket

from quads.tools.helpers import get_or_create_event_loop


class Netcat:
    """Python 'netcat like' module"""

    def __init__(self, ip, port=22, loop=None):
        self.ip = ip
        self.port = port
        self.buff = ""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.loop = loop if loop else get_or_create_event_loop()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def health_check(self, timeout=15):
        try:
            self.socket.settimeout(timeout)
            await self.connect()
        except (
            socket.timeout,
            TimeoutError,
            ConnectionResetError,
            ConnectionRefusedError,
        ):
            return False
        return True

    async def read(self, length=1024):
        """Read 1024 bytes off the socket"""
        sock_recv = await self.loop.sock_recv(self.socket, length)
        return sock_recv

    async def read_until(self, data):
        """Read data into the buffer until we have data"""
        while data not in self.buff:
            self.buff += await self.loop.sock_recv(self.socket, 1024)

        pos = self.buff.find(data)
        return_val = self.buff[: pos + len(data)]
        self.buff = self.buff[pos + len(data) :]

        return return_val

    async def write(self, data):
        await self.loop.sock_sendall(self.socket, data)

    async def connect(self):
        await self.loop.sock_connect(self.socket, (self.ip, self.port))

    async def close(self):
        self.socket.close()
