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
        self.ws = await connect(connect_string).__await_impl__()
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
            if data["t"] == "broadcast":
                if not (cb := self.topics.get(data["topic"])):
                    continue
                get_event_loop().create_task(cb(data["data"]))
            elif data["t"] == "response":
                i = data["request_id"]
                if not (cb := self.topics.get(i)):
                    continue
                get_event_loop().create_task(cb(data["response"]))
                del self.topics[i]

    async def request(self, callback, broadcaster, data):
        await self.wait_until_start()
        if not self.online:
            return
        req = urandom(32).hex()
        self.topics[req] = callback
        await self.ws.send(jdumps({"t": "request", "request_id": req, "br_name": broadcaster, "request_data": data}))

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
        self.callback = None
        self.running = False
        self.online = True

    async def start(self, connect_string):
        self.ws = await connect(connect_string).__await_impl__()
        get_event_loop().create_task(self._run())

    async def wait_until_start(self) -> None:
        while not self.running:
            await asleep(0.1)

    async def _handle_request(self, request_id, data):
        if not self.callback:
            await self.ws.send(jdumps({"t": "response", "request_id": request_id, "response": None}))
            return
        task = get_event_loop().create_task(self.callback(data))
        res = await gather(task)
        if not res:
            res = [None]
        res = res[0]
        await self.ws.send(jdumps({"t": "response", "request_id": request_id, "response": res}))

    async def _run(self):
        await self.ws.send(jdumps({"role": "b", "name": self.name}))
        self.running = True
        while True:
            try:
                data = jloads(await self.ws.recv())
            except:
                break
            if data["t"] == "request":
                get_event_loop().create_task(self._handle_request(data["request_id"], data["data"]))

    async def broadcast(self, topic: str, data: dict) -> None:
        await self.wait_until_start()
        if self.online:
            await self.ws.send(jdumps({"t": "broadcast", "topic": topic, "data": data}))

    def set_callback(self, callback):
        self.callback = callback