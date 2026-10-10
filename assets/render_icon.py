# /// script
# requires-python = ">=3.11"
# dependencies = ["resvg-py==0.5.0"]
# ///
"""Render the PNGs in this folder from icon.svg.

- icon.png, 512x512, the fallback for clients that show no SVG.
- social-preview.png, 1280x640, the image GitHub shows when the repository
  link is shared. It is uploaded by hand under Settings > General > Social
  preview, there is no API for it.
- architecture.png, how a question travels from you through an MCP client
  and this server to Yahoo and back, for the README and SPECS.md §3.

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
ARCHITECTURE_WIDTH, ARCHITECTURE_HEIGHT = 1280, 380

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


def _step(x: int, w: int, title: str, *lines: str, kind: str) -> str:
    """One station on the way, a title and a line or two under it.

    server is this project, outside is not its code, plain is the rest.
    """
    y, h = 170, 150
    stroke = {"server": "#2DD4BF", "outside": "#64748B", "plain": "#64748B"}[kind]
    fill = "#2DD4BF" if kind == "server" else "#1E293B"
    opacity = "0.12" if kind == "server" else "1"
    dash = ' stroke-dasharray="7 6"' if kind == "outside" else ""
    cx = x + w / 2
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" '
        f'fill-opacity="{opacity}" stroke="{stroke}" stroke-width="2"{dash}/>',
        f'<text x="{cx}" y="{y + 56}" font-size="26" font-weight="700" '
        f'fill="#F8FAFC" text-anchor="middle">{title}</text>',
    ]
    for i, line in enumerate(lines):
        mono = line.startswith("`")
        family = ' font-family="Consolas, Menlo, monospace"' if mono else ""
        parts.append(
            f'<text x="{cx}" y="{y + 92 + 26 * i}" font-size="17" fill="#CBD5E1" '
            f'text-anchor="middle"{family}>{line.strip("`")}</text>'
        )
    return "".join(parts)


def _hop(x1: int, x2: int, ask: str, reply: str) -> str:
    """A request going right above, its reply coming back below."""
    mid = (x1 + x2) / 2
    return (
        f'<path d="M{x1 + 4} 222 H{x2 - 4}" stroke="#2DD4BF" stroke-width="2.5" '
        'marker-end="url(#go)"/>'
        f'<path d="M{x2 - 4} 268 H{x1 + 4}" stroke="#94A3B8" stroke-width="2.5" '
        'marker-end="url(#back)"/>'
        f'<text x="{mid}" y="210" font-size="15" fill="#5EEAD4" '
        f'text-anchor="middle">{ask}</text>'
        f'<text x="{mid}" y="292" font-size="15" fill="#CBD5E1" '
        f'text-anchor="middle">{reply}</text>'
    )


def _architecture() -> str:
    """How a question gets answered, for a person rather than for the code.

    The modules and which may import which stay in SPECS.md §3 as a table.
    """
    markers = "".join(
        f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0 0L10 5L0 10z" fill="{colour}"/></marker>'
        for name, colour in (("go", "#2DD4BF"), ("back", "#94A3B8"))
    )
    body = [
        '<text x="640" y="80" font-size="30" font-weight="700" fill="#F8FAFC" '
        'text-anchor="middle">How a question gets answered</text>',
        '<text x="640" y="114" font-size="18" fill="#94A3B8" '
        'text-anchor="middle">read-only, no Yahoo account, no API key</text>',
        _step(40, 200, "You", "ask in plain", "language", kind="plain"),
        _step(310, 230, "MCP client", "for example", "Claude", kind="plain"),
        _step(
            630,
            300,
            "This server",
            "`benethos-yahoo-finance-mcp`",
            "fetches, keeps it compact",
            kind="server",
        ),
        _step(
            1020,
            220,
            "Yahoo Finance",
            "unofficial endpoints,",
            "via yfinance",
            kind="outside",
        ),
        _hop(240, 310, "question", "answer"),
        _hop(540, 630, "tool call", "JSON"),
        _hop(930, 1020, "request", "data"),
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ARCHITECTURE_WIDTH}" '
        f'height="{ARCHITECTURE_HEIGHT}" viewBox="0 0 {ARCHITECTURE_WIDTH} '
        f'{ARCHITECTURE_HEIGHT}"><defs>{markers}</defs>'
        '<rect width="100%" height="100%" fill="#121A2A"/>'
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
