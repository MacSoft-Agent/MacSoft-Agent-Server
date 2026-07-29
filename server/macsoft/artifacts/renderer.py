from __future__ import annotations

import json
import html
import shutil
import struct
import subprocess
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


def _chromium_executable(configured: str = "") -> Path:
    candidates = [
        Path(configured) if configured else None,
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    raise ChartRenderError("chromium_not_found")


def _dashboard_html(render_input: dict[str, Any]) -> str:
    points = render_input.get("dataset", {}).get("points", [])
    if not isinstance(points, list) or not points:
        raise ChartRenderError("empty_dataset")
    labels = [str(item.get("key", "")) for item in points]
    try:
        values = [float(item.get("value", 0)) for item in points]
    except (TypeError, ValueError) as error:
        raise ChartRenderError("invalid_dataset_value") from error
    maximum = max(values) or 1.0
    chart_left, chart_top, chart_width, chart_height = 92, 205, 1018, 330
    step = chart_width / max(1, len(values))
    bars: list[str] = []
    labels_svg: list[str] = []
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        width = max(24, min(76, step * 0.58))
        height = max(2, value / maximum * (chart_height - 24))
        x = chart_left + index * step + (step - width) / 2
        y = chart_top + chart_height - height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="10" fill="url(#bar)"/>'
            f'<text x="{x + width / 2:.1f}" y="{y - 12:.1f}" text-anchor="middle" class="value">{value:g}</text>'
        )
        labels_svg.append(
            f'<text x="{x + width / 2:.1f}" y="{chart_top + chart_height + 35:.1f}" text-anchor="middle" class="axis">{html.escape(label)}</text>'
        )
    grid = "".join(
        f'<line x1="{chart_left}" y1="{chart_top + chart_height * i / 4:.1f}" x2="{chart_left + chart_width}" y2="{chart_top + chart_height * i / 4:.1f}" class="grid"/>'
        for i in range(5)
    )
    title = html.escape(str(render_input.get("title") or "Chart"))
    summary = html.escape(str(render_input.get("summary") or ""))
    total = int(sum(values))
    peak_index = values.index(max(values))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}html,body{{margin:0;width:1200px;height:675px;overflow:hidden;background:#111c35;font-family:Segoe UI,Arial,sans-serif;color:#f7fbff}}
.wrap{{padding:48px 56px}}h1{{font-size:34px;margin:0 0 8px;font-weight:700;letter-spacing:-.5px}}p{{margin:0;color:#9eb0ce;font-size:16px}}
.kpis{{position:absolute;right:58px;top:42px;display:flex;gap:14px}}.kpi{{min-width:142px;padding:15px 18px;border:1px solid #304467;border-radius:16px;background:#192846}}.kpi b{{display:block;font-size:25px;color:#31d5a2}}.kpi span{{font-size:12px;color:#91a4c5;text-transform:uppercase;letter-spacing:1px}}
svg{{position:absolute;left:40px;top:108px}}.grid{{stroke:#304566;stroke-width:1}}.axis{{fill:#94a8c8;font-size:14px}}.value{{fill:#eaf4ff;font-size:14px;font-weight:600}}
</style></head><body><div class="wrap"><h1>{title}</h1><p>{summary}</p></div>
<div class="kpis"><div class="kpi"><b>{total}</b><span>Invoices shown</span></div><div class="kpi"><b>{html.escape(labels[peak_index])}</b><span>Peak month</span></div></div>
<svg width="1160" height="555" viewBox="0 0 1160 555"><defs><linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#35e2ad"/><stop offset="1" stop-color="#168b87"/></linearGradient></defs>{grid}{''.join(bars)}{''.join(labels_svg)}</svg>
</body></html>"""


def render_chart_chromium(
    render_input: dict[str, Any],
    png_target: Path,
    *,
    pdf_target: Path | None = None,
    chromium_path: str = "",
) -> None:
    executable = _chromium_executable(chromium_path)
    png_target.parent.mkdir(parents=True, exist_ok=True)
    html_path = png_target.parent / "chart.html"
    profile = png_target.parent / "chromium-profile"
    html_path.write_text(_dashboard_html(render_input), encoding="utf-8")
    common = [
        str(executable),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        f"--user-data-dir={profile}",
    ]
    screenshot = subprocess.run(
        [*common, "--window-size=1200,675", f"--screenshot={png_target}", html_path.as_uri()],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if screenshot.returncode != 0 or not png_target.is_file():
        raise ChartRenderError("chromium_png_failed")
    if pdf_target is not None:
        printed = subprocess.run(
            [*common, "--no-pdf-header-footer", f"--print-to-pdf={pdf_target}", html_path.as_uri()],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if printed.returncode != 0 or not pdf_target.is_file():
            raise ChartRenderError("chromium_pdf_failed")
    shutil.rmtree(profile, ignore_errors=True)


def load_render_input(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ChartRenderError("invalid_render_input")
    return value
