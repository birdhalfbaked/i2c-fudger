from __future__ import annotations

import struct

from sensor_test.models import CType, Endianness, FieldSpec, SchemaSpec
from sensor_test.schema_decode import decode_frame


def test_mpu9150_register_block_decode_big_endian_int16() -> None:
    # MPU-9150 register block at 0x3B is big-endian int16 values:
    # accel_x, accel_y, accel_z, temp, gyro_x, gyro_y, gyro_z
    raw = struct.pack(">hhhhhhh", 1, -2, 3, 100, -101, 102, -103)

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

    decoded = decode_frame(schema, raw).decoded
    assert decoded["accel_x"] == 1
    assert decoded["accel_y"] == -2
    assert decoded["accel_z"] == 3
    assert decoded["temp_raw"] == 100
    assert decoded["gyro_x"] == -101
    assert decoded["gyro_y"] == 102
    assert decoded["gyro_z"] == -103

