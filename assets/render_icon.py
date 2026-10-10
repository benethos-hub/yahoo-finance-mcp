# /// script
# requires-python = ">=3.11"
# dependencies = ["resvg-py==0.5.0"]
# ///
"""Render the PNGs in this folder from icon.svg.

- icon.png, 512x512, the fallback for clients that show no SVG.
- social-preview.png, 1280x640, the image GitHub shows when the repository
  link is shared. It is uploaded by hand under Settings > General > Social
  preview, there is no API for it.
- architecture.png, the diagram in SPECS.md §3: how a call travels from the
  client through the layers to Yahoo, and what sits beside that path.

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
ARCHITECTURE_PNG = HERE / "architecture.png"
ARCHITECTURE_WIDTH, ARCHITECTURE_HEIGHT = 1280, 900

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


def _box(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    *lines: str,
    kind: str,
    logs: bool = False,
) -> str:
    """One unit of the diagram: a module name and a line or two about it.

    main is a step on a call's path, side sits beside it, outside is not
    this project's code. logs marks a unit that writes through logbook/.
    """
    stroke = {"main": "#2DD4BF", "side": "#64748B", "outside": "#64748B"}[kind]
    dash = ' stroke-dasharray="6 5"' if kind == "outside" else ""
    fill = "#2DD4BF" if kind == "main" else "#1E293B"
    opacity = "0.10" if kind == "main" else "1"
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" '
        f'fill-opacity="{opacity}" stroke="{stroke}" stroke-width="1.5"{dash}/>',
        f'<text x="{x + 20}" y="{y + 32}" font-family="Consolas, Menlo, monospace" '
        f'font-size="20" fill="#F8FAFC">{title}</text>',
    ]
    for i, line in enumerate(lines):
        parts.append(
            f'<text x="{x + 20}" y="{y + 58 + 22 * i}" font-size="16" '
            f'fill="#94A3B8">{line}</text>'
        )
    if logs:
        parts.append(
            f'<rect x="{x + w - 70}" y="{y + 14}" width="54" height="24" rx="12" '
            'fill="#94A3B8" fill-opacity="0.15" stroke="#94A3B8" stroke-opacity="0.6"/>'
            f'<text x="{x + w - 43}" y="{y + 31}" font-size="14" fill="#CBD5E1" '
            'text-anchor="middle">logs</text>'
        )
    return "".join(parts)


def _arrow(path: str, colour: str) -> str:
    marker = "ar-main" if colour == "#2DD4BF" else "ar-side"
    return (
        f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2" '
        f'marker-end="url(#{marker})"/>'
    )


def _label(x: int, y: int, text: str, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="15" fill="#CBD5E1" '
        f'text-anchor="{anchor}">{text}</text>'
    )


def _architecture() -> str:
    """SPECS.md §3 as a picture: the main column is a tool call's path."""
    main, side = "#2DD4BF", "#64748B"
    markers = "".join(
        f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0L10 5L0 10z" fill="{colour}"/></marker>'
        for name, colour in (("ar-main", main), ("ar-side", side))
    )
    body = [
        _box(
            40,
            60,
            320,
            110,
            "MCP client",
            "Claude Desktop, Claude Code,",
            "Cursor, VS Code, n8n, ...",
            kind="outside",
        ),
        _box(
            470,
            60,
            420,
            110,
            "transport/",
            "stdio.py, http.py",
            "Host allow-list, optional bearer token",
            kind="main",
            logs=True,
        ),
        _box(
            470,
            220,
            420,
            80,
            "server.py",
            "MCPServer, instructions, refused arguments",
            kind="main",
            logs=True,
        ),
        _box(
            470,
            350,
            420,
            100,
            "tools/&lt;subject&gt;.py",
            "parameters, descriptions, titles",
            "register_tool: read-only hints, a log line",
            kind="main",
            logs=True,
        ),
        _box(
            470,
            500,
            420,
            100,
            "yahoo/&lt;subject&gt;.py",
            "every yfinance call, the error mapping",
            "ToolError, SymbolNotFoundError, RateLimitError",
            kind="main",
            logs=True,
        ),
        _box(
            470,
            650,
            420,
            70,
            "yfinance",
            "the library, not this project",
            kind="outside",
        ),
        _box(
            470,
            770,
            420,
            70,
            "query1/2.finance.yahoo.com",
            "Yahoo's unofficial endpoints",
            kind="outside",
        ),
        _box(
            40,
            220,
            320,
            100,
            "cli.py",
            "settings, log, cache,",
            "builds the server",
            kind="side",
            logs=True,
        ),
        _box(
            40,
            360,
            320,
            122,
            "settings.py",
            "every YF_MCP_* variable and flag,",
            "resolved once by cli.py, read by",
            "server, transport and cache",
            kind="side",
        ),
        _box(
            40,
            512,
            320,
            100,
            "logbook/",
            "every log line, stderr only,",
            "written by each unit marked logs",
            kind="side",
        ),
        _box(960, 440, 280, 80, "formatting.py", "pandas to compact JSON", kind="side"),
        _box(
            960,
            560,
            280,
            80,
            "cache.py",
            "opt-in SQLite, per-tool TTLs",
            kind="side",
            logs=True,
        ),
        _arrow("M360 115 H466", main),
        _label(415, 104, "stdio / HTTP", "middle"),
        _arrow("M680 170 V216", main),
        _arrow("M680 300 V346", main),
        _arrow("M680 450 V496", main),
        _arrow("M680 600 V646", main),
        _arrow("M680 720 V766", main),
        _label(694, 750, "HTTPS"),
        _arrow("M360 260 H466", side),
        _label(415, 250, "builds", "middle"),
        _arrow("M200 360 V324", side),
        _arrow("M890 530 H925 V480 H956", side),
        _arrow("M890 580 H925 V600 H956", side),
        '<text x="40" y="664" font-size="15" fill="#94A3B8">'
        "<tspan>Each unit imports only what the</tspan>"
        '<tspan x="40" dy="22">layer table in SPECS.md §3 allows,</tspan>'
        '<tspan x="40" dy="22">tests/test_layers.py checks it.</tspan></text>',
        '<text x="40" y="744" font-size="15" fill="#94A3B8">'
        "<tspan>stdout carries the MCP stream,</tspan>"
        '<tspan x="40" dy="22">so every log line goes to stderr.</tspan></text>',
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ARCHITECTURE_WIDTH}" '
        f'height="{ARCHITECTURE_HEIGHT}" viewBox="0 0 {ARCHITECTURE_WIDTH} '
        f'{ARCHITECTURE_HEIGHT}"><defs>{markers}</defs>'
        f'<rect width="100%" height="100%" fill="#121A2A"/>'
        '<g font-family="Segoe UI, Inter, Helvetica, Arial, sans-serif">'
        f"{''.join(body)}</g></svg>"
    )


def render(svg: str, width: int, height: int, target: Path) -> None:
    png = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height)
    target.write_bytes(png)
    print(f"{target.name}: {width}x{height}, {len(png)} bytes")


def main() -> None:
    render(ICON_SVG.read_text(encoding="utf-8"), ICON_SIZE, ICON_SIZE, ICON_PNG)
    preview = PREVIEW.format(icon=_icon(80, 200, 240), chips=_chips(380, 478))
    render(preview, PREVIEW_WIDTH, PREVIEW_HEIGHT, PREVIEW_PNG)
    render(_architecture(), ARCHITECTURE_WIDTH, ARCHITECTURE_HEIGHT, ARCHITECTURE_PNG)


if __name__ == "__main__":
    main()
