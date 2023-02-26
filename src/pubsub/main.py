from asyncio import Future, gather, get_event_loop, run
from websockets import serve
from json import loads as jloads, dumps as jdumps

subscribers = []
broadcasters = []

class Subscriber:
    def __init__(self, ws):
        self.ws = ws
        self.topics = []

    def sub(self, topic):
        if topic.lower() not in self.topics:
            self.topics.append(topic.lower())

    def unsub(self, topic):
        if topic.lower() in self.topics:
            self.topics.remove(topic.lower())

class Broadcaster:
    def __init__(self, ws, name):
        self.ws = ws
        self.name = name

async def handle_subscriber(sub, client):
    while True:
        try:
            data = jloads(await client.recv())
        except:
            break
        if data["t"] == "request":
            br_name = data["br_name"]
            req = data["request_id"]
            br = [b for b in broadcasters if b.name == br_name]
            if not br:
                await client.send(jdumps({"t": "response", "request_id": req, "response": None}))
                continue
            br = br[0]
            sub.sub(req)
            await br.ws.send(jdumps({"t": "request", "request_id": req, "data": data["request_data"]}))
        elif data["t"] == "subscribe":
            sub.sub(data["topic"])
        elif data["t"] == "unsubscribe":
            sub.unsub(data["topic"])

async def broadcast(clients, data, topic):
    data = jdumps({"t": "broadcast", "topic": topic, "data": data})
    for client in clients:
        await client.ws.send(data)

async def handle_broadcaster(client):
    while True:
        try:
            data = jloads(await client.recv())
        except:
            break
        if data["t"] == "broadcast":
            subs = [sub for sub in subscribers if data["topic"] in sub.topics]
            get_event_loop().create_task(broadcast(subs, data["data"], data["topic"]))
        elif data["t"] == "response":
            req = data["request_id"]
            sub = [sub for sub in subscribers if req in sub.topics]
            if not sub:
                continue
            sub = sub[0]
            sub.unsub(req)
            await sub.ws.send(jdumps({"t": "response", "request_id": req, "response": data["response"]}))

async def handle(client):
    data = jloads(await client.recv())
    if data["role"] == "b":
        cl = Broadcaster(client, data["name"])
        broadcasters.append(cl)
        task = get_event_loop().create_task(handle_broadcaster(client))
    else:
        cl = Subscriber(client)
        subscribers.append(cl)
        task = get_event_loop().create_task(handle_subscriber(cl, client))
    await gather(task)
    if data["role"] == "b":
        broadcasters.remove(cl)
    else:
        subscribers.remove(cl)

async def main():
    async with serve(handle, "0.0.0.0", 5050):
        await Future()

run(main())