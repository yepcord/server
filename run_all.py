from subprocess import Popen, PIPE as sPIPE, STDOUT as sSTDOUT
from os import environ
from time import sleep
from threading import Thread

environ["PYTHONUNBUFFERED"] = "1"

class Process:
    def __init__(self, name, app=None, port=None, file=None, wd="."):
        self.name = name
        self.app = app
        self.port = port
        self.file = file
        self.wd = wd
        self.output = []
        self._process = None
        self.started = False
        self.astarted = False

    def _run(self, cmd):
        self._process = Popen(cmd.split(" "), stdout=sPIPE, stdin=sPIPE, cwd=self.wd, stderr=sSTDOUT)
        out = ""
        while self._process.poll() is None:
            try:
                o = self._process.stdout.read(1).decode("utf8")
            except UnicodeDecodeError:
                continue
            if o == "":
                continue
            if o in ["\r", "\n"]:
                if "Application startup complete" in out:
                    self.started = True
                self.output.append(out)
                out = ""
                continue
            out += o

    def run(self):
        if not self.app:
            cmd = f"python -u {self.file}"
        else:
            cmd = f"python -u -m uvicorn {self.app} --ssl-keyfile=ssl/key.pem --ssl-certfile=ssl/cert.pem --reload --reload-dir server" + (f" --port {self.port}" if self.port else "")
        self.running = True
        Thread(target=self._run, args=(cmd,)).start()

    def stop(self, kill=False):
        if self._process.poll():
            return
        if kill:
            self._process.kill()
            return
        self._process.terminate()
        sleep(5)
        self.stop(True)

processes = [
    Process("IMT", file="main.py", wd="internal/message_transport"),
    Process("HttpApi", app="server.http_api.main:app", port=8000),
    Process("Gateway", app="server.gateway.main:app", port=8001),
    Process("CDN", app="server.cdn.main:app", port=8003),
    Process("RemoteAuth", app="server.remote_auth.main:app", port=8002),
    Process("Client", app="client.main:app", port=8080),
]

skip_logs = [
    "The --reload flag should not be used in production on Windows.",
    "Waiting for application startup.",
    "Started server process",
    "Started reloader process",
    "Will watch for changes in these directories:",
    "Uvicorn running on",
    "WatchGodReload detected file change in",
    "Application startup complete"
]

def main():
    for p in processes:
        p.run()

    while True:
        try:
            for p in processes:
                while p.output:
                    s = p.output.pop(0)
                    if "WatchGodReload detected file change in" in s:
                    	print(f"[{p.name}] Reloading...")
                    elif "Application startup complete" in s and (p.started and p.astarted):
                    	print(f"[{p.name}] Reload complete.")
                    sk = False
                    for _a in skip_logs:
                        if _a in s:
                            sk = True
                            break
                    if s and not sk:
                        print(f"[{p.name}] {s}")
                if p.started and not p.astarted:
                    p.astarted = True
                    print(f"[{p.name}] Application startup complete!")
        except KeyboardInterrupt:
            break

    for p in processes:
        Thread(target=p.stop).start()

if __name__ == "__main__":
    main()