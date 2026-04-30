from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Endianness(str, Enum):
    little = "little"
    big = "big"


class CType(str, Enum):
    uint8 = "uint8"
    uint16 = "uint16"
    uint32 = "uint32"
    uint64 = "uint64"
    int8 = "int8"
    int16 = "int16"
    int32 = "int32"
    int64 = "int64"


class FieldSpec(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    type: CType
    count: Annotated[int, Field(ge=1, le=4096)] = 1
    endianness: Endianness = Endianness.little

    @field_validator("name")
    @classmethod
    def _name_is_identifierish(cls, v: str) -> str:
        v2 = v.strip()
        if not v2:
            raise ValueError("name cannot be empty")
        return v2


class SchemaSpec(BaseModel):
    fields: list[FieldSpec] = Field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        from sensor_test.schema_decode import field_nbytes

        return sum(field_nbytes(f) for f in self.fields)


class I2CConfig(BaseModel):
    enabled: bool = False

    # Allows exercising the system without hardware.
    transport: Literal["linux_i2c", "mock_mpu9150"] = "linux_i2c"

    pins_preset: str = "i2c-1"
    bus: Annotated[int, Field(ge=0, le=32)] = 1

    # 7-bit address (0..127). UI will typically accept hex; API accepts int.
    address: Annotated[int, Field(ge=0, le=127)] = 0x00

    # Common sensor pattern: set register pointer then read N bytes.
    register: Annotated[int, Field(ge=0, le=0xFFFF)] = 0x00
    register_width: Literal[1, 2] = 1

    read_length: Annotated[int, Field(ge=1, le=4096)] = 16
    poll_hz: Annotated[float, Field(gt=0.0, le=1000.0)] = 10.0

    @model_validator(mode="after")
    def _reg_fits_width(self) -> "I2CConfig":
        if self.register_width == 1 and self.register > 0xFF:
            raise ValueError("register must fit in 1 byte when register_width=1")
        return self

