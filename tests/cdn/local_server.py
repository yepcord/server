from contextlib import contextmanager


class Server:
    @contextmanager
    def run_in_thread(self):
        yield


def local_server() -> Server:
    return Server()
