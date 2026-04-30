from __future__ import annotations

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from sensor_test.frame_processing import frame_to_view
from sensor_test.i2c_reader import I2CReader, RawFrame
from sensor_test.models import CType, Endianness, FieldSpec, I2CConfig, SchemaSpec
from sensor_test.pi_presets import PI_I2C_PRESETS, preset_by_key


def create_app() -> FastAPI:
    reader = I2CReader()
    schema: SchemaSpec | None = None

    ws_clients: set[WebSocket] = set()
    stop_event = asyncio.Event()

    async def broadcast_loop() -> None:
        while not stop_event.is_set():
            # Blocking queue get in a threadpool to avoid stalling the event loop.
            frame: RawFrame = await asyncio.to_thread(reader.events.get)
            view = frame_to_view(frame, schema)
            payload = view.__dict__

            dead: list[WebSocket] = []
            for ws in ws_clients:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                ws_clients.discard(ws)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(broadcast_loop())
        try:
            yield
        finally:
            stop_event.set()
            reader.stop()
            task.cancel()
            with suppress(Exception):
                await task

    app = FastAPI(title="sensor-test", version="0.1.0", lifespan=lifespan)

    # Dev-friendly defaults; adjust for deployment as needed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Optional: serve built frontend from the backend (single-process deploy).
    # If `frontend/dist` exists, mount it at `/` and fall back to `index.html`.
    # `.../src/sensor_test/web/app.py` -> parents[0]=web,1=sensor_test,2=src,3=repo_root
    repo_root = Path(__file__).resolve().parents[3]
    dist_dir = (repo_root / "frontend" / "dist").resolve()
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

        @app.get("/")
        def _index() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/presets")
    def presets() -> list[dict[str, Any]]:
        return [
            {
                "key": p.key,
                "bus": p.bus,
                "sda_gpio": p.sda_gpio,
                "scl_gpio": p.scl_gpio,
                "label": p.label,
            }
            for p in PI_I2C_PRESETS
        ]

    @app.post("/api/examples/mpu9150/apply")
    def apply_mpu9150_example() -> dict[str, Any]:
        """
        Apply a known-good configuration + schema for MPU-9150 register block reads:
        - Device addr: 0x68
        - Register: 0x3B
        - Read length: 14 bytes
        - Fields: accel/temp/gyro int16 big-endian
        """
        nonlocal schema

        cfg = reader.get_config()
        cfg.address = 0x68
        cfg.register = 0x3B
        cfg.register_width = 1
        cfg.read_length = 14
        cfg.poll_hz = 50.0
        reader.set_config(cfg)

        schema = SchemaSpec(
            fields=[
                FieldSpec(name="accel_x", type=CType.int16, count=1, endianness=Endianness.big),
                FieldSpec(name="accel_y", type=CType.int16, count=1, endianness=Endianness.big),
                FieldSpec(name="accel_z", type=CType.int16, count=1, endianness=Endianness.big),
                FieldSpec(name="temp_raw", type=CType.int16, count=1, endianness=Endianness.big),
                FieldSpec(name="gyro_x", type=CType.int16, count=1, endianness=Endianness.big),
                FieldSpec(name="gyro_y", type=CType.int16, count=1, endianness=Endianness.big),
                FieldSpec(name="gyro_z", type=CType.int16, count=1, endianness=Endianness.big),
            ]
        )
        return {"ok": True, "config": cfg.model_dump(), "schema": schema.model_dump(), "total_bytes": schema.total_bytes}

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        cfg = reader.get_config()
        return cfg.model_dump()

    @app.put("/api/config")
    def put_config(cfg: I2CConfig) -> dict[str, Any]:
        preset = preset_by_key(cfg.pins_preset)
        if preset is not None:
            cfg.bus = preset.bus
        reader.set_config(cfg)
        return {"ok": True, "config": cfg.model_dump()}

    @app.get("/api/schema")
    def get_schema() -> dict[str, Any]:
        return {
            "schema": None if schema is None else schema.model_dump(),
            "total_bytes": 0 if schema is None else schema.total_bytes,
        }

    @app.put("/api/schema")
    def put_schema(new_schema: SchemaSpec) -> dict[str, Any]:
        nonlocal schema
        schema = new_schema
        return {"ok": True, "schema": schema.model_dump(), "total_bytes": schema.total_bytes}

    @app.post("/api/control/start")
    def start() -> dict[str, Any]:
        cfg = reader.get_config()
        cfg.enabled = True
        reader.set_config(cfg)
        reader.start()
        return {"ok": True, "running": True}

    @app.post("/api/control/stop")
    def stop() -> dict[str, Any]:
        cfg = reader.get_config()
        cfg.enabled = False
        reader.set_config(cfg)
        reader.stop()
        return {"ok": True, "running": False}

    @app.get("/api/frames")
    def frames(limit: int = 200) -> dict[str, Any]:
        fs = reader.frames(limit=limit)
        views = [frame_to_view(f, schema).__dict__ for f in fs]
        return {"frames": views}

    @app.websocket("/api/stream")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        ws_clients.add(ws)
        try:
            while True:
                # Keep connection alive; we don't require client messages.
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_clients.discard(ws)
        except Exception:
            ws_clients.discard(ws)

    return app


app = create_app()

