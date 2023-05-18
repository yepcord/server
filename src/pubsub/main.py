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
        if data["t"] == "subscribe":
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