from contextlib import contextmanager
from ftplib import FTP
from threading import Thread
from time import sleep

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer


class FtpServer(ThreadedFTPServer):
    def __init__(self, port: int=9021):
        self._port = port
        authorizer = DummyAuthorizer()
        authorizer.add_user('root', '123456', 'tests/files/', perm='elradfmwMT')
        handler = FTPHandler
        handler.authorizer = authorizer
        super().__init__(('127.0.0.1', port), handler)

    def is_started(self) -> bool:
        try:
            f = FTP()
            f.connect("127.0.0.1", self._port)
            f.quit()
            return True
        except (ConnectionRefusedError, AttributeError):
            return False

    @contextmanager
    def run_in_thread(self):
        thread = Thread(target=self.serve_forever)
        thread.start()
        try:
            while not self.is_started():
                sleep(1e-3)
            yield
        finally:
            self.close_all()
            thread.join()


def ftp_server(port: int=9021) -> FtpServer:
    return FtpServer(port=port)
