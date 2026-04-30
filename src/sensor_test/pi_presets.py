from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class I2CPinsPreset:
    key: str
    bus: int
    sda_gpio: int
    scl_gpio: int
    label: str


# Raspberry Pi: standard I2C is provided by hardware controller(s), and Linux
# exposes them as /dev/i2c-<bus>. The SDA/SCL GPIOs are fixed per bus.
#
# These presets are informational + help pick the correct bus.
PI_I2C_PRESETS: list[I2CPinsPreset] = [
    I2CPinsPreset(
        key="i2c-1",
        bus=1,
        sda_gpio=2,
        scl_gpio=3,
        label="I2C-1 (SDA=GPIO2, SCL=GPIO3) [typical]",
    ),
    I2CPinsPreset(
        key="i2c-0",
        bus=0,
        sda_gpio=0,
        scl_gpio=1,
        label="I2C-0 (SDA=GPIO0, SCL=GPIO1) [varies by model/config]",
    ),
]


def preset_by_key(key: str) -> I2CPinsPreset | None:
    for p in PI_I2C_PRESETS:
        if p.key == key:
            return p
    return None

