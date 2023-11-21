"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import warnings
from json import dumps, loads
from typing import Union, Optional, Callable, Coroutine

from async_timeout import timeout
from propan import RabbitBroker, RedisBroker, SQSBroker, KafkaBroker, NatsBroker
from websockets.client import connect
from websockets.legacy.client import WebSocketClientProtocol
from websockets.legacy.server import WebSocketServer
from websockets.protocol import State
from websockets.server import serve

from .config import Config


class WsServer:
    def __init__(self, url: str):
        self._url = url
        self._connections: set[WebSocketClientProtocol] = set()
        self._server: Optional[WebSocketServer] = None
        self._run_event = asyncio.Event()

    async def _broadcast(self, message: str, exclude=None) -> None:  # pragma: no cover
        for connection in self._connections:
            if connection.state is not State.OPEN or connection == exclude:
                continue
            await connection.send(message)

    async def _handle(self, client) -> None:
        self._connections.add(client)
        async for message in client:
            await self._broadcast(message, exclude=client)

        self._connections.remove(client)

    async def _run(self) -> None:
        # Using 'wait_forever' because 'await asyncio.Future()' raises RuntimeError and, tbh, I don't know why
        async def wait_forever():
            while True:
                await asyncio.sleep(2 ** 31 - 1)

        url = self._url.replace("ws://", "")
        host = url.split(":")[0]
        port = int(url.split(":")[1])
        try:
            async with serve(self._handle, host, port) as server:
                self._server = server
                self._run_event.set()
                await wait_forever()
        except OSError:  # pragma: no cover
            self._run_event.set()
        self._server = None  # pragma: no cover

    async def run(self):
        asyncio.get_event_loop().create_task(self._run())
        async with timeout(5):
            await self._run_event.wait()
        self._run_event.clear()

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()


class WsBroker:
    def __init__(self, url: str = "ws://127.0.0.1:5055", **kwargs):
        self._connection: Optional[WebSocketClientProtocol] = None
        self._url = url
        self._handlers: dict[str, set[Coroutine]] = {}
        self._server = None
        self._run_event = asyncio.Event()

    def _reinitialize(self):
        self._connection = None
        self._server = None
        self._run_event = asyncio.Event()

    async def _try_run_server(self) -> None:
        self._server = WsServer(self._url)
        await self._server.run()

    async def _real_run_client(self) -> None:  # pragma: no cover
        async with connect(self._url) as ws:
            self._connection = ws
            self._run_event.set()
            async for message in ws:
                await self._handle_message(message)

        self._connection = None

    async def _run_client(self) -> None:
        for _ in range(5):
            try:
                await self._real_run_client()
                break
            except:  # pragma: no cover
                await asyncio.sleep(.5)

    async def _handle_message(self, message: str) -> None:  # pragma: no cover
        data = loads(message)
        if "channel" not in data or "message" not in data:
            return
        channel = data["channel"]
        for handler in self._handlers.get(channel, []):
            asyncio.get_running_loop().create_task(handler(data["message"]))

    async def start(self) -> None:
        if self._connection is not None and not self._connection.closed:  # pragma: no cover
            return
        self._reinitialize()

        await self._try_run_server()
        asyncio.get_running_loop().create_task(self._run_client())
        await self._run_event.wait()
        self._run_event.clear()

    async def close(self) -> None:
        if self._connection is not None and not self._connection.closed:  # pragma: no cover
            await self._connection.close()
            self._connection = None
        if self._server is not None:
            await self._server.close()
            self._server = None

    async def publish(self, message: dict, channel: str) -> None:
        if self._connection is None or self._connection.closed:  # pragma: no cover
            await self.start()
        await self._connection.send(dumps({
            "channel": channel,
            "message": message,
        }))

    def handle(self, channel: str) -> Callable:  # pragma: no cover
        def _handle(func):
            if channel not in self._handlers:
                self._handlers[channel] = set()
            self._handlers[channel].add(func)
            return func

        return _handle


_brokers = {
    "rabbitmq": RabbitBroker,
    "redis": RedisBroker,
    "sqs": SQSBroker,
    "kafka": KafkaBroker,
    "nats": NatsBroker,
    "ws": WsBroker,
}


def getBroker() -> Union[RabbitBroker, RedisBroker, SQSBroker, KafkaBroker, NatsBroker, WsBroker]:
    broker_type = Config.MESSAGE_BROKER["type"].lower()
    assert broker_type in ("rabbitmq", "redis", "sqs", "kafka", "nats", "ws",), \
        "MESSAGE_BROKER.type must be one of ('rabbitmq', 'redis', 'sqs', 'kafka', 'nats', 'ws')"

    if broker_type == "ws":
        warnings.warn("'ws' message broker type is used. This message broker type should not be used in production!")

    return _brokers[broker_type](**Config.MESSAGE_BROKER[broker_type], logger=None)
