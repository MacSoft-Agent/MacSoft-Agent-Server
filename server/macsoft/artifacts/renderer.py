from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any


class ChartRenderError(RuntimeError):
    pass


def _chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    path.write_bytes(png)


def render_chart_png(render_input: dict[str, Any], target: Path) -> None:
    """Dependency-free Foundation renderer for lifecycle verification.

    The production ECharts backend remains behind the external Renderer gate.
    """

    points = render_input.get("dataset", {}).get("points", [])
    if not isinstance(points, list) or not points:
        raise ChartRenderError("empty_dataset")
    values: list[float] = []
    for point in points:
        try:
            values.append(float(str(point["value"])))
        except (KeyError, TypeError, ValueError) as error:
            raise ChartRenderError("invalid_dataset_value") from error

    width, height = 960, 540
    pixels = bytearray(width * height * 3)
    top, bottom = (29, 45, 78), (22, 34, 61)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(width):
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes(color)

    def set_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes(color)

    left, right, upper, lower = 74, width - 48, 58, height - 70
    grid = (48, 72, 111)
    for index in range(7):
        y = upper + (lower - upper) * index // 6
        for x in range(left, right + 1):
            set_pixel(x, y, grid)
    grid_columns = min(12, max(2, len(values)))
    for index in range(grid_columns):
        x = left + (right - left) * index // max(1, grid_columns - 1)
        for y in range(upper, lower + 1):
            set_pixel(x, y, grid)

    low, high = min(values), max(values)
    span = high - low or 1.0
    coords: list[tuple[int, int]] = []
    for index, value in enumerate(values):
        x = left + (right - left) * index // max(1, len(values) - 1)
        y = lower - int((value - low) / span * (lower - upper - 24))
        coords.append((x, y))

    fill, line = (26, 122, 111), (45, 210, 166)
    if len(coords) == 1:
        coords.append((right, coords[0][1]))
    for index in range(len(coords) - 1):
        x0, y0 = coords[index]
        x1, y1 = coords[index + 1]
        for x in range(x0, x1 + 1):
            t = 0 if x1 == x0 else (x - x0) / (x1 - x0)
            y = int(y0 + (y1 - y0) * t)
            for fill_y in range(y + 3, lower, 3):
                set_pixel(x, fill_y, fill)
            for dy in (-2, -1, 0, 1, 2):
                set_pixel(x, y + dy, line)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_png(target, width, height, pixels)


def load_render_input(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ChartRenderError("invalid_render_input")
    return value
