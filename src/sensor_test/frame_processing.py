from __future__ import annotations

from dataclasses import dataclass

from sensor_test.i2c_reader import RawFrame
from sensor_test.models import SchemaSpec
from sensor_test.schema_decode import SchemaDecodeError, decode_frame


@dataclass(frozen=True)
class FrameView:
    ts_unix: float
    bus: int
    address: int
    register: int
    read_length: int
    raw_hex: str
    error: str | None
    decoded: dict[str, object] | None
    decode_error: str | None


def frame_to_view(frame: RawFrame, schema: SchemaSpec | None) -> FrameView:
    raw_hex = frame.raw.hex()
    decoded: dict[str, object] | None = None
    decode_error: str | None = None

    if schema is not None and frame.error is None:
        try:
            decoded = decode_frame(schema, frame.raw).decoded
        except SchemaDecodeError as e:
            decode_error = str(e)

    return FrameView(
        ts_unix=frame.ts_unix,
        bus=frame.bus,
        address=frame.address,
        register=frame.register,
        read_length=frame.read_length,
        raw_hex=raw_hex,
        error=frame.error,
        decoded=decoded,
        decode_error=decode_error,
    )

