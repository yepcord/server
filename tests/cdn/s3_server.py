from contextlib import contextmanager
from threading import Thread
from time import sleep

from fake_s3.main import app as s3app
from fake_s3.file_store import FileStore
import uvicorn
from uvicorn import Config


class AsgiServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    @contextmanager
    def run_in_thread(self):
        thread = Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()


def s3_server(port: int=10001) -> AsgiServer:
    s3app.config["store"] = FileStore("tests/files")
    config = Config(s3app, host="127.0.0.1", port=port, log_level="warning")
    return AsgiServer(config=config)
