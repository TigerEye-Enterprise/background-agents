"""Wait for the private Modal Access sidecar before starting the Rail 3 sandbox."""

import runpy
import socket
import time


def main() -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("rail3-access", 8788), timeout=1):
                break
        except OSError:
            time.sleep(0.5)
    else:
        raise SystemExit("Rail 3 Access sidecar did not start")
    runpy.run_module("sandbox_runtime.entrypoint", run_name="__main__")


if __name__ == "__main__":
    main()
