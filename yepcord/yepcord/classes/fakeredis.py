from asyncio import sleep, set_event_loop, new_event_loop
from collections import defaultdict
from threading import Thread
from time import time
from typing import Optional, Union


class Value:
    __slots__ = ("ex", "value")

    def __init__(self, value: str, ex: int):
        self.value = value
        self.ex = ex

    def expired(self) -> bool:
        return 0 < self.ex < time()


class FakeRedis:
    def __init__(self, interval: int = 30):
        self._interval = interval
        self._kv: dict[str, Value] = {}
        self._sets: dict[str, set] = defaultdict(set)
        self._exp = defaultdict(set)
        self._thread: Union[Thread, None] = None

    def run(self):
        self._thread = Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def _run_thread(self):
        loop = new_event_loop()
        set_event_loop(loop)
        loop.run_until_complete(self._run_task())

    def pipeline(self):
        return self

    async def _run_task(self):
        last = int(time() // self._interval - 5)
        while self._thread is not None:
            await sleep(self._interval)
            this = int(time() // self._interval - 1)
            for i in range(last, this + 1):
                exp = self._exp.pop(i, set())
                for key in exp:
                    if key in self._kv and self._kv[key].expired():
                        del self._kv[key]

                del exp
            last = this

    async def set(self, key: str, value: str, ex: int = None, nx: bool=False):
        exp_time = int(time() + ex) if ex is not None else 0
        val = self._kv.get(key, None)
        if val is not None and not val.expired() and nx:
            return

        if val is not None and val.ex > 0:
            self._exp[exp_time // self._interval].remove(key)

        self._kv[key] = Value(value, exp_time)
        if ex is not None:
            self._exp[exp_time // self._interval].add(key)

    async def expire(self, key: str, ex: int) -> None:
        if key not in self._kv:
            return

        val = self._kv[key]
        val.ex = int(time() + ex)
        self._exp[val.ex // self._interval].add(key)

    async def get(self, key: str) -> Optional[str]:
        val = self._kv.pop(key, None)
        if val is None or val.expired():
            return

        return val.value

    async def delete(self, key: str):
        if key in self._kv:
            del self._kv[key]

    async def sadd(self, name: str, *values: str):
        self._sets[name].update(values)

    async def srem(self, name: str, *values: str):
        self._sets[name].difference_update(set(values))

    async def sismember(self, name: str, value: str):
        return value in self._sets[name]

    async def execute(self):
        pass

    async def close(self):
        self._thread = None
