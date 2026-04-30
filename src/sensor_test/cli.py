from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import shutil
import signal
import sys
from pathlib import Path


def _repo_root() -> Path:
    # `.../src/sensor_test/cli.py` -> parents[0]=sensor_test,1=src,2=repo_root
    return Path(__file__).resolve().parents[2]


async def _run_process(*args: str, cwd: Path) -> asyncio.subprocess.Process:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )
    return proc


async def _pipe_output(prefix: str, proc: asyncio.subprocess.Process) -> None:
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            return
        try:
            txt = line.decode(errors="replace").rstrip("\n")
        except Exception:
            txt = repr(line)
        print(f"[{prefix}] {txt}")


async def dev(host: str, backend_port: int, frontend_port: int) -> int:
    root = _repo_root()
    frontend_dir = root / "frontend"

    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm not found on PATH (required for frontend dev server).")

    # Backend: run uvicorn using current interpreter (works under `uv run ...`).
    backend_args = [
        sys.executable,
        "-m",
        "uvicorn",
        "sensor_test.web.app:app",
        "--host",
        host,
        "--port",
        str(backend_port),
    ]

    # Frontend: Vite dev server. Use --host for LAN access.
    frontend_args = [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(frontend_port),
    ]

    backend = await _run_process(*backend_args, cwd=root)
    frontend = await _run_process(*frontend_args, cwd=frontend_dir)

    pipes = [
        asyncio.create_task(_pipe_output("backend", backend)),
        asyncio.create_task(_pipe_output("frontend", frontend)),
    ]

    stop = asyncio.Event()

    def _handle_sig(*_: object) -> None:
        stop.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, _handle_sig)
        loop.add_signal_handler(signal.SIGTERM, _handle_sig)

    await asyncio.wait(
        [asyncio.create_task(backend.wait()), asyncio.create_task(frontend.wait()), asyncio.create_task(stop.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for p in (backend, frontend):
        if p.returncode is None:
            with contextlib.suppress(Exception):
                p.terminate()

    await asyncio.gather(*(p.wait() for p in (backend, frontend)), return_exceptions=True)
    for t in pipes:
        t.cancel()

    return max(backend.returncode or 0, frontend.returncode or 0)


def serve(host: str, port: int) -> int:
    # Single-process deploy: build frontend to `frontend/dist` and then run this.
    import uvicorn

    uvicorn.run("sensor_test.web.app:app", host=host, port=port, reload=False)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(prog="sensor-test", description="Run the I2C web reader.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_dev = sub.add_parser("dev", help="Run backend + frontend dev server together.")
    p_dev.add_argument("--host", default="0.0.0.0", help="Bind host (use 0.0.0.0 for LAN).")
    p_dev.add_argument("--backend-port", type=int, default=8000)
    p_dev.add_argument("--frontend-port", type=int, default=5173)

    p_serve = sub.add_parser("serve", help="Serve backend (and built frontend if present).")
    p_serve.add_argument("--host", default="0.0.0.0", help="Bind host (use 0.0.0.0 for LAN).")
    p_serve.add_argument("--port", type=int, default=8000)

    args = p.parse_args()

    if args.cmd == "dev":
        code = asyncio.run(dev(args.host, args.backend_port, args.frontend_port))
        raise SystemExit(code)
    if args.cmd == "serve":
        raise SystemExit(serve(args.host, args.port))


if __name__ == "__main__":
    main()

