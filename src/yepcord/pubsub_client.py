from websockets import connect
from json import loads as jloads, dumps as jdumps
from asyncio import get_event_loop, gather, sleep as asleep
from os import urandom

class Client:
    def __init__(self):
        self.ws = None
        self.topics = {}
        self.running = False
        self.online = True

    async def start(self, connect_string):
        try:
            self.ws = await connect(connect_string).__await_impl__()
        except ConnectionRefusedError:
            self.online = False
            self.running = True
            return
        get_event_loop().create_task(self._run())

    async def wait_until_start(self):
        while not self.running:
            await asleep(0.1)

    async def _run(self):
        await self.ws.send(jdumps({"role": "s"}))
        self.running = True
        while True:
            try:
                data = jloads(await self.ws.recv())
            except:
                break
            if not (cb := self.topics.get(data["topic"])):
                continue
            get_event_loop().create_task(cb(data["data"]))

    async def subscribe(self, topic, callback):
        await self.wait_until_start()
        if not self.online:
            return
        topic = topic.lower()
        if topic not in self.topics:
            self.topics[topic] = callback
            await self.ws.send(jdumps({"t": "subscribe", "topic": topic}))

    async def unsubscribe(self, topic):
        await self.wait_until_start()
        if not self.online:
            return
        topic = topic.lower()
        if topic in self.topics:
            del self.topics[topic]
            await self.ws.send(jdumps({"t": "unsubscribe", "topic": topic}))

class Broadcaster:
    def __init__(self, name):
        self.ws = None
        self.name = name
        self.running = False
        self.online = True

    async def start(self, connect_string):
        try:
            self.ws = await connect(connect_string).__await_impl__()
        except ConnectionRefusedError:
            self.online = False
            self.running = True
            return
        await self.ws.send(jdumps({"role": "b", "name": self.name}))
        self.running = True

    async def wait_until_start(self):
        while not self.running:
            await asleep(0.1)

    async def broadcast(self, topic, data):
        await self.wait_until_start()
        if self.online:
            await self.ws.send(jdumps({"t": "broadcast", "topic": topic, "data": data}))
