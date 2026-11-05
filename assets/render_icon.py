# /// script
# requires-python = ">=3.11"
# dependencies = ["resvg-py==0.5.0"]
# ///
"""Render the PNGs from brand/icon.svg.

The brand assets follow the rules of the benethos-hub organisation (its
.github repository): brand/icon.svg is the source, and both PNGs next to it
are exported from it.

- brand/icon.png, 512x512, the fallback for clients that show no SVG.
- brand/social-preview.png, 1280x640, the image GitHub shows when the
  repository link is shared. It is uploaded by hand under Settings > General
  > Social preview, there is no API for it.
- architecture.png, how a question travels from you through an MCP client
  and this server to Yahoo and back, for the README and SPECS.md §3.

icon.svg and icon.png directly in this folder are the copies from before the
brand folder. The MCP Registry entries up to 0.8.5 point at them, so they
stay, and this script no longer writes them.

Run it after every change to the SVG or to the text below and commit the
results together, the organisation's brand check fails when a PNG is older
than the SVG:

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
BRAND = HERE / "brand"
ICON_SVG = BRAND / "icon.svg"
ICON_PNG = BRAND / "icon.png"
ICON_SIZE = 512
PREVIEW_PNG = BRAND / "social-preview.png"
PREVIEW_WIDTH, PREVIEW_HEIGHT = 1280, 640
ARCHITECTURE_PNG = HERE / "architecture.png"
ARCHITECTURE_WIDTH, ARCHITECTURE_HEIGHT = 1280, 470

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


# Plain line symbols on a 24 unit grid, for the stations that are not this
# project. No logo of anyone else: the project is unofficial, and neither
# Yahoo's nor a client's look belongs in its picture.
SYMBOLS = {
    "person": (
        '<circle cx="12" cy="8" r="4"/>'
        '<path d="M4.5 21c0-4.2 3.3-7.5 7.5-7.5s7.5 3.3 7.5 7.5"/>'
    ),
    "chat": (
        '<path d="M4 5.5h16a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5H10'
        'l-4.5 3.5v-3.5H4A1.5 1.5 0 0 1 2.5 16V7A1.5 1.5 0 0 1 4 5.5z"/>'
        '<path d="M7.5 11.5h.01M12 11.5h.01M16.5 11.5h.01" stroke-width="2.6"/>'
    ),
    "market": ('<path d="M3 3.5V20.5H21"/><path d="M7 15.5l4-4.5 3.5 3 5.5-7"/>'),
}

# Where the stations sit, and the height of the arrows between them.
CARD_Y, CARD_H = 170, 240
GO_Y, BACK_Y = CARD_Y + 96, CARD_Y + 146


def _badge(cx: float, symbol: str, colour: str) -> str:
    """A symbol in a round plate at the top of a station."""
    cy, size = CARD_Y + 58, 34
    return (
        f'<circle cx="{cx}" cy="{cy}" r="32" fill="{colour}" fill-opacity="0.14" '
        f'stroke="{colour}" stroke-opacity="0.5" stroke-width="1.5"/>'
        f'<svg x="{cx - size / 2}" y="{cy - size / 2}" width="{size}" '
        f'height="{size}" viewBox="0 0 24 24" fill="none" stroke="{colour}" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{SYMBOLS[symbol]}</svg>"
    )


def _step(x: int, w: int, title: str, *lines: str, kind: str, symbol: str) -> str:
    """One station on the way: its symbol, a title and a line or two under it.

    server is this project and carries its icon, outside is not its code,
    plain is the rest.
    """
    server = kind == "server"
    stroke = "#2DD4BF" if server else "#475569"
    fill = "url(#card-server)" if server else "url(#card)"
    dash = ' stroke-dasharray="7 6"' if kind == "outside" else ""
    width = "2.5" if server else "1.5"
    cx = x + w / 2
    badge = (
        _icon(round(cx - 36), CARD_Y + 22, 72)
        if server
        else _badge(cx, symbol, "#94A3B8" if kind == "outside" else "#5EEAD4")
    )
    parts = [
        f'<rect x="{x}" y="{CARD_Y}" width="{w}" height="{CARD_H}" rx="20" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash} '
        'filter="url(#lift-card)"/>',
        badge,
        f'<text x="{cx}" y="{CARD_Y + 134}" font-size="26" font-weight="700" '
        f'fill="#F8FAFC" text-anchor="middle">{title}</text>',
    ]
    for i, line in enumerate(lines):
        mono = line.startswith("`")
        family = ' font-family="Consolas, Menlo, monospace"' if mono else ""
        parts.append(
            f'<text x="{cx}" y="{CARD_Y + 170 + 26 * i}" font-size="17" '
            f'fill="#CBD5E1" text-anchor="middle"{family}>{line.strip("`")}</text>'
        )
    return "".join(parts)


def _hop(x1: int, x2: int, ask: str, reply: str) -> str:
    """A request going right above, its reply coming back below."""
    mid = (x1 + x2) / 2
    return (
        f'<path d="M{x1 + 6} {GO_Y} H{x2 - 6}" stroke="#2DD4BF" stroke-width="2.5" '
        'marker-end="url(#go)"/>'
        f'<path d="M{x2 - 6} {BACK_Y} H{x1 + 6}" stroke="#94A3B8" stroke-width="2.5" '
        'marker-end="url(#back)"/>'
        f'<text x="{mid}" y="{GO_Y - 12}" font-size="15" fill="#5EEAD4" '
        f'text-anchor="middle">{ask}</text>'
        f'<text x="{mid}" y="{BACK_Y + 24}" font-size="15" fill="#CBD5E1" '
        f'text-anchor="middle">{reply}</text>'
    )


def _pills(cx: int, y: int, *labels: str) -> str:
    """Rounded labels in one centred row. Widths are estimated from the text."""
    widths = [round(len(label) * 8.6) + 36 for label in labels]
    gap = 12
    x = cx - (sum(widths) + gap * (len(labels) - 1)) / 2
    parts = []
    for label, width in zip(labels, widths, strict=True):
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="32" rx="16" '
            'fill="#2DD4BF" fill-opacity="0.12" '
            'stroke="#2DD4BF" stroke-opacity="0.45"/>'
            f'<text x="{x + width / 2}" y="{y + 22}" font-size="16" fill="#E2E8F0" '
            f'text-anchor="middle">{label}</text>'
        )
        x += width + gap
    return "".join(parts)


def _architecture() -> str:
    """How a question gets answered, for a person rather than for the code.

    The modules and which may import which stay in SPECS.md §3 as a table.
    """
    defs = "".join(
        f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0 0L10 5L0 10z" fill="{colour}"/></marker>'
        for name, colour in (("go", "#2DD4BF"), ("back", "#94A3B8"))
    )
    defs += (
        '<linearGradient id="arch-bg" x1="0" y1="0" x2="0.35" y2="1">'
        '<stop offset="0%" stop-color="#26334A"/>'
        '<stop offset="100%" stop-color="#121A2A"/></linearGradient>'
        '<linearGradient id="arch-line" x1="0" y1="1" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#2DD4BF"/>'
        '<stop offset="100%" stop-color="#4ADE80"/></linearGradient>'
        '<linearGradient id="card" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#2A3750"/>'
        '<stop offset="100%" stop-color="#1B2538"/></linearGradient>'
        '<linearGradient id="card-server" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1F4A52"/>'
        '<stop offset="100%" stop-color="#17303C"/></linearGradient>'
        '<filter id="lift-card" x="-10%" y="-10%" width="120%" height="125%">'
        '<feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#0B1120" '
        'flood-opacity="0.55"/></filter>'
    )
    body = [
        (
            '<polyline points="0,458 260,442 520,454 780,426 1020,436 1280,396" '
            'fill="none" stroke="url(#arch-line)" stroke-width="3" opacity="0.16"/>'
        ),
        (
            '<text x="640" y="66" font-size="32" font-weight="700" fill="#F8FAFC" '
            'text-anchor="middle">How a question gets answered</text>'
        ),
        _pills(640, 92, "read-only", "no Yahoo account", "no API key"),
        _step(
            40, 200, "You", "ask in plain", "language", kind="plain", symbol="person"
        ),
        _step(
            310, 230, "MCP client", "for example", "Claude", kind="plain", symbol="chat"
        ),
        _step(
            630,
            300,
            "This server",
            "`benethos-yahoo-finance-mcp`",
            "fetches, keeps it compact",
            kind="server",
            symbol="",
        ),
        _step(
            1020,
            220,
            "Yahoo Finance",
            "unofficial endpoints,",
            "via yfinance",
            kind="outside",
            symbol="market",
        ),
        _hop(240, 310, "question", "answer"),
        _hop(540, 630, "tool call", "JSON"),
        _hop(930, 1020, "request", "data"),
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ARCHITECTURE_WIDTH}" '
        f'height="{ARCHITECTURE_HEIGHT}" viewBox="0 0 {ARCHITECTURE_WIDTH} '
        f'{ARCHITECTURE_HEIGHT}"><defs>{defs}</defs>'
        '<rect width="100%" height="100%" fill="url(#arch-bg)"/>'
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
