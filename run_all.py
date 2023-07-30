from os import environ
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from time import sleep

environ["PYTHONUNBUFFERED"] = "1"


class Process:
    def __init__(self, name, app=None, port=None, file=None, wd=".", *, disable_logs=False):
        self.name = name
        self.app = app
        self.port = port
        self.file = file
        self.wd = wd
        self.disable_logs = disable_logs
        self.output = []
        self._process = None
        self.started = False
        self.astarted = False

    def _run(self, cmd):
        self._process = Popen(cmd.split(" "), stdout=PIPE, stdin=PIPE, cwd=self.wd, stderr=STDOUT)
        out = ""
        while self._process.poll() is None:
            try:
                o = self._process.stdout.read(1).decode("utf8")
            except UnicodeDecodeError:
                continue
            if o == "" or self.disable_logs:
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
            cmd = f"python -u -m uvicorn --reload --reload-dir ./src/ --reload-exclude 'tests/generated/*.py' " \
                  f"{self.app} --forwarded-allow-ips='*' --ssl-keyfile=ssl/key.pem --ssl-certfile=ssl/cert.pem " \
                  f"--host 0.0.0.0" + (f" --port {self.port}" if self.port else "")
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
    Process("HttpApi", app="src.rest_api.main:app", port=8000),
    Process("Gateway", app="src.gateway.main:app", port=8001),
    Process("CDN", app="src.cdn.main:app", port=8003),
    Process("RemoteAuth", app="src.remote_auth.main:app", port=8002),
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
