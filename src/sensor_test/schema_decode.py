from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

from sensor_test.models import CType, Endianness, FieldSpec, SchemaSpec


class SchemaDecodeError(Exception):
    pass


_CTYPE_TO_STRUCT: dict[CType, tuple[str, int]] = {
    CType.uint8: ("B", 1),
    CType.uint16: ("H", 2),
    CType.uint32: ("I", 4),
    CType.uint64: ("Q", 8),
    CType.int8: ("b", 1),
    CType.int16: ("h", 2),
    CType.int32: ("i", 4),
    CType.int64: ("q", 8),
}


def field_nbytes(field: FieldSpec) -> int:
    _, size = _CTYPE_TO_STRUCT[field.type]
    return size * field.count


@dataclass(frozen=True)
class DecodedFrame:
    decoded: dict[str, Any]
    total_bytes_used: int


def _endian_prefix(e: Endianness) -> str:
    return "<" if e == Endianness.little else ">"


def decode_frame(schema: SchemaSpec, raw: bytes) -> DecodedFrame:
    """
    Decode bytes using a simple packed layout:
    fields are concatenated in order; no padding/alignment.
    """
    out: dict[str, Any] = {}
    offset = 0
    for field in schema.fields:
        code, size = _CTYPE_TO_STRUCT[field.type]
        nbytes = size * field.count
        if offset + nbytes > len(raw):
            raise SchemaDecodeError(
                f"raw frame too short for field '{field.name}': "
                f"need {nbytes} bytes at offset {offset}, have {len(raw) - offset}"
            )

        fmt = _endian_prefix(field.endianness) + (code * field.count)
        try:
            values = struct.unpack_from(fmt, raw, offset)
        except struct.error as e:
            raise SchemaDecodeError(f"struct decode failed for field '{field.name}': {e}") from e

        out[field.name] = values[0] if field.count == 1 else list(values)
        offset += nbytes

    return DecodedFrame(decoded=out, total_bytes_used=offset)

