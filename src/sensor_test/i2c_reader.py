from __future__ import annotations

import math
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass
from queue import Queue
from typing import Deque, Optional

from smbus2 import SMBus, i2c_msg

from sensor_test.models import I2CConfig


@dataclass(frozen=True)
class RawFrame:
    ts_unix: float
    bus: int
    address: int
    register: int
    read_length: int
    raw: bytes
    error: str | None = None


class I2CReader:
    """
    Poll an I2C device using register-then-read and store raw frames.

    - Acquisition is isolated from schema decoding: raw bytes are captured first.
    - Uses a background thread so the FastAPI event loop stays responsive.
    """

    def __init__(self, max_frames: int = 2000) -> None:
        self._lock = threading.Lock()
        self._frames: Deque[RawFrame] = deque(maxlen=max_frames)
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # New frames are pushed here for streaming consumers.
        self.events: Queue[RawFrame] = Queue(maxsize=10_000)

        self._config = I2CConfig()

    def get_config(self) -> I2CConfig:
        with self._lock:
            return self._config.model_copy(deep=True)

    def set_config(self, cfg: I2CConfig) -> None:
        with self._lock:
            self._config = cfg

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run, name="I2CReader", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            t = self._thread
            self._thread = None
        if t is not None:
            t.join(timeout=2.0)

    def frames(self, limit: int = 200) -> list[RawFrame]:
        with self._lock:
            if limit <= 0:
                return []
            return list(self._frames)[-limit:]

    def _push_frame(self, frame: RawFrame) -> None:
        with self._lock:
            self._frames.append(frame)
        # Non-blocking best effort for streaming.
        try:
            self.events.put_nowait(frame)
        except Exception:
            pass

    def _read_once(self, cfg: I2CConfig) -> RawFrame:
        ts = time.time()
        if cfg.transport == "mock_mpu9150":
            # Produce deterministic, realistic-ish register payload for MPU-9150
            # accel/gyro/temp register block starting at 0x3B (14 bytes, big-endian).
            #
            # Layout:
            #   accel_x, accel_y, accel_z, temp, gyro_x, gyro_y, gyro_z (int16 BE)
            t = ts
            ax = int(16384 * math.sin(t * 0.7))
            ay = int(16384 * math.sin(t * 0.9 + 1.0))
            az = int(16384 * math.cos(t * 0.6))
            temp = int(340 * (25.0 - 36.53) + 0)  # ~25C in raw units
            gx = int(5000 * math.sin(t * 1.3))
            gy = int(5000 * math.cos(t * 1.1))
            gz = int(5000 * math.sin(t * 0.8 + 2.0))
            raw14 = struct.pack(">hhhhhhh", ax, ay, az, temp, gx, gy, gz)
            # Also simulate AK8975C read starting at ST1 (0x02):
            # ST1 + (HXL..HZH) + ST2 => 8 bytes.
            if cfg.address == 0x0C and cfg.register == 0x02 and cfg.read_length >= 8:
                mx = int(2000 * math.sin(t * 0.5))
                my = int(2000 * math.cos(t * 0.7))
                mz = int(2000 * math.sin(t * 0.6 + 1.5))
                # AK8975C outputs little-endian low/high bytes.
                mag = struct.pack("<hhh", mx, my, mz)
                data = bytes([0x01]) + mag + bytes([0x00])  # ST1=DRDY, ST2=0
                data = data[: cfg.read_length].ljust(cfg.read_length, b"\x00")
            else:
                data = raw14[: cfg.read_length].ljust(cfg.read_length, b"\x00")
            return RawFrame(
                ts_unix=ts,
                bus=cfg.bus,
                address=cfg.address,
                register=cfg.register,
                read_length=cfg.read_length,
                raw=data,
            )

        try:
            reg_bytes = (
                bytes([cfg.register & 0xFF])
                if cfg.register_width == 1
                else bytes([(cfg.register >> 8) & 0xFF, cfg.register & 0xFF])
            )
            write = i2c_msg.write(cfg.address, reg_bytes)
            read = i2c_msg.read(cfg.address, cfg.read_length)
            with SMBus(cfg.bus) as bus:
                if cfg.cycle_write is not None:
                    bus.write_byte_data(cfg.cycle_write.address, cfg.cycle_write.register, cfg.cycle_write.value)
                    if cfg.cycle_delay_ms:
                        time.sleep(cfg.cycle_delay_ms / 1000.0)
                bus.i2c_rdwr(write, read)
            data = bytes(read)
            return RawFrame(
                ts_unix=ts,
                bus=cfg.bus,
                address=cfg.address,
                register=cfg.register,
                read_length=cfg.read_length,
                raw=data,
            )
        except Exception as e:  # pragma: no cover (depends on HW)
            return RawFrame(
                ts_unix=ts,
                bus=cfg.bus,
                address=cfg.address,
                register=cfg.register,
                read_length=cfg.read_length,
                raw=b"",
                error=str(e),
            )

    def _run(self) -> None:
        next_t = time.perf_counter()
        did_setup = False
        while True:
            with self._lock:
                running = self._running
                cfg = self._config.model_copy(deep=True)
            if not running:
                return

            if not did_setup and cfg.transport != "mock_mpu9150" and cfg.setup_writes:
                try:
                    with SMBus(cfg.bus) as bus:
                        for w in cfg.setup_writes:
                            bus.write_byte_data(w.address, w.register, w.value)
                    did_setup = True
                except Exception:
                    # If setup fails, keep trying; capture error in the next frame.
                    pass

            frame = self._read_once(cfg)
            self._push_frame(frame)

            # Rate control
            period = 1.0 / max(cfg.poll_hz, 1e-6)
            next_t += period
            sleep_s = next_t - time.perf_counter()
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                # If we're behind, reset schedule to avoid runaway backlog.
                next_t = time.perf_counter()

