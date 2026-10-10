# /// script
# requires-python = ">=3.11"
# dependencies = ["resvg-py==0.5.0"]
# ///
"""Render the PNGs in this folder from icon.svg.

- icon.png, 512x512, the fallback for clients that show no SVG.
- social-preview.png, 1280x640, the image GitHub shows when the repository
  link is shared. It is uploaded by hand under Settings > General > Social
  preview, there is no API for it.

Run it after every change to the SVG or to the text below and commit the
results together:

    uv run assets/render_icon.py

uv reads the dependency above and runs the script in a throwaway environment,
so the renderer never enters the project's own dependencies. resvg is pinned
because another version may draw the same SVG a few pixels differently. The
preview's text is set in the system's sans-serif font, so it was rendered on
Windows (Segoe UI) and looks a little different elsewhere.
"""

from __future__ import annotations

import re
from pathlib import Path

import resvg_py

HERE = Path(__file__).resolve().parent
ICON_SVG = HERE / "icon.svg"
ICON_PNG = HERE / "icon.png"
ICON_SIZE = 512
PREVIEW_PNG = HERE / "social-preview.png"
PREVIEW_WIDTH, PREVIEW_HEIGHT = 1280, 640

# The preview's words. Unofficial is spelled out and nothing borrows Yahoo's
# look: the icon and the colours are the project's own.
PREVIEW = """\
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640"
     viewBox="0 0 1280 640">
  <defs>
    <linearGradient id="sp-bg" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0%" stop-color="#26334A"/>
      <stop offset="100%" stop-color="#121A2A"/>
    </linearGradient>
    <linearGradient id="sp-line" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0%" stop-color="#2DD4BF"/>
      <stop offset="100%" stop-color="#4ADE80"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="640" fill="url(#sp-bg)"/>
  <polyline points="0,628 260,612 520,624 780,596 1020,606 1280,566"
            fill="none" stroke="url(#sp-line)" stroke-width="3" opacity="0.18"/>
  {icon}
  <g font-family="Segoe UI, Inter, Helvetica, Arial, sans-serif">
    <text x="380" y="200" font-family="Consolas, Menlo, monospace" font-size="26"
          fill="#2DD4BF">benethos-yahoo-finance-mcp</text>
    <g font-size="56" font-weight="700" fill="#F8FAFC">
      <text x="380" y="272">Unofficial Yahoo Finance</text>
      <text x="380" y="338">MCP Server</text>
    </g>
    <g font-size="25" fill="#CBD5E1">
      <text x="380" y="398">Quotes, history, financials, analyst data, options</text>
      <text x="380" y="434"
            >and a stock screener for Claude and other MCP clients.</text>
    </g>
    {chips}
    <text x="380" y="584" font-size="18" fill="#64748B"
          >Read-only, via yfinance. Not affiliated with Yahoo.</text>
  </g>
</svg>
"""

CHIPS = ("PyPI", "Docker", "Claude Desktop extension", "MCP Registry")


def _chips(x: int, y: int) -> str:
    """Rounded labels in one row. Widths are estimated from the text length."""
    parts = []
    for label in CHIPS:
        width = round(len(label) * 9.3) + 40
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="38" rx="19" '
            'fill="#2DD4BF" fill-opacity="0.12" '
            'stroke="#2DD4BF" stroke-opacity="0.45"/>'
            f'<text x="{x + width / 2}" y="{y + 26}" font-size="19" fill="#E2E8F0" '
            f'text-anchor="middle">{label}</text>'
        )
        x += width + 14
    return "".join(parts)


def _icon(x: int, y: int, size: int) -> str:
    """icon.svg as a nested svg, its ids prefixed so they cannot clash."""
    svg = ICON_SVG.read_text(encoding="utf-8")
    svg = re.sub(r'id="([^"]+)"', r'id="ic-\1"', svg)
    svg = re.sub(r"url\(#([^)]+)\)", r"url(#ic-\1)", svg)
    return re.sub(
        r"<svg [^>]*>",
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 256 256">',
        svg,
        count=1,
    )


def render(svg: str, width: int, height: int, target: Path) -> None:
    png = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height)
    target.write_bytes(png)
    print(f"{target.name}: {width}x{height}, {len(png)} bytes")


def main() -> None:
    render(ICON_SVG.read_text(encoding="utf-8"), ICON_SIZE, ICON_SIZE, ICON_PNG)
    preview = PREVIEW.format(icon=_icon(80, 200, 240), chips=_chips(380, 478))
    render(preview, PREVIEW_WIDTH, PREVIEW_HEIGHT, PREVIEW_PNG)


if __name__ == "__main__":
    main()
