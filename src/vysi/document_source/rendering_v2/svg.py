from __future__ import annotations

import textwrap
from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class PreviewItem:
    native_refs: tuple[str, ...]
    text: str
    role: str = "text"


@dataclass(frozen=True)
class PreviewElement:
    native_refs: tuple[str, ...]
    x: float
    y: float
    width: float
    height: float
    role: str
    clipped: bool = False


@dataclass(frozen=True)
class SvgPreview:
    payload: bytes
    elements: tuple[PreviewElement, ...]
    serialized_refs: tuple[str, ...]
    visible_refs: tuple[str, ...]
    clipped_refs: tuple[str, ...]
    omitted_refs: tuple[str, ...]


def _xml_text(value: str) -> str:
    safe = "".join(
        char if char in {"\t", "\n", "\r"} or ord(char) >= 0x20 else "�" for char in value
    )
    return escape(safe, quote=False)


def _wrap(value: str, max_chars: int) -> list[str]:
    expanded = value.expandtabs(4)
    logical = expanded.splitlines() or [expanded]
    wrapped: list[str] = []
    for line in logical:
        if not line:
            wrapped.append("⟦empty⟧")
            continue
        parts = textwrap.wrap(
            line,
            width=max(1, max_chars),
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        )
        wrapped.extend(parts or ["⟦empty⟧"])
    return wrapped


def paginate_text_preview(
    *,
    title: str,
    items: list[PreviewItem],
    width: int = 794,
    height: int = 1123,
    font_size: int = 14,
    line_height: int = 20,
    margin: int = 48,
    footer: str | None = None,
) -> list[SvgPreview]:
    # Estimation conservatrice pour une police monospace. Elle garantit que le
    # texte ne quitte pas la surface même si le moteur SVG substitue la police.
    usable_width = max(1, width - margin * 2)
    max_chars = max(1, int(usable_width / (font_size * 0.68)))
    first_y = margin + 34
    footer_room = 34 if footer else 12
    capacity = max(1, (height - first_y - margin - footer_room) // line_height)

    visual_lines: list[tuple[PreviewItem, str]] = []
    for item in items:
        for segment in _wrap(item.text, max_chars):
            visual_lines.append((item, segment))
    if not visual_lines:
        visual_lines.append((PreviewItem((), "⟦no renderable text⟧", "empty"), "⟦no renderable text⟧"))

    pages: list[SvgPreview] = []
    for page_index in range(0, len(visual_lines), capacity):
        chunk = visual_lines[page_index : page_index + capacity]
        nodes = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect x="0" y="0" width="100%" height="100%" fill="white"/>',
            f'<text x="{margin}" y="{margin}" font-family="monospace" font-size="16" font-weight="bold">{_xml_text(title)} — {len(pages)+1}</text>',
        ]
        elements: list[PreviewElement] = []
        serialized: set[str] = set()
        visible: set[str] = set()
        y = first_y
        for item, segment in chunk:
            nodes.append(
                f'<text x="{margin}" y="{y}" font-family="monospace" font-size="{font_size}" xml:space="preserve">{_xml_text(segment)}</text>'
            )
            estimated_width = min(usable_width, max(font_size * 0.68, len(segment) * font_size * 0.68))
            if item.native_refs:
                serialized.update(item.native_refs)
                visible.update(item.native_refs)
                elements.append(
                    PreviewElement(
                        item.native_refs,
                        float(margin),
                        float(y - font_size),
                        float(estimated_width),
                        float(line_height),
                        item.role,
                        False,
                    )
                )
            y += line_height
        if footer:
            nodes.append(
                f'<text x="{margin}" y="{height - 22}" font-family="monospace" font-size="10">{_xml_text(footer)}</text>'
            )
        nodes.append("</svg>")
        pages.append(
            SvgPreview(
                ("\n".join(nodes) + "\n").encode("utf-8"),
                tuple(elements),
                tuple(sorted(serialized)),
                tuple(sorted(visible)),
                (),
                (),
            )
        )
    return pages


def svg_table_page(
    *,
    title: str,
    cells: list[tuple[tuple[str, ...], int, int, str]],
    width: int = 1123,
    height: int = 794,
    max_columns: int = 12,
    max_rows: int = 26,
) -> SvgPreview:
    left, top = 36, 70
    columns = max(1, min(max((col for _, _, col, _ in cells), default=0) + 1, max_columns))
    rows = max(1, min(max((row for _, row, _, _ in cells), default=0) + 1, max_rows))
    cell_w = max(65, (width - left * 2) // columns)
    cell_h = max(22, min(30, (height - top - 30) // rows))
    max_chars = max(1, int((cell_w - 8) / (11 * 0.68)))
    nodes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="36" font-family="monospace" font-size="18" font-weight="bold">{_xml_text(title)}</text>',
    ]
    elements: list[PreviewElement] = []
    serialized: set[str] = set()
    visible: set[str] = set()
    clipped: set[str] = set()
    for refs, row, col, value in cells:
        if row >= rows or col >= columns:
            continue
        x = left + col * cell_w
        y = top + row * cell_h
        nodes.append(
            f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="none" stroke="#777" stroke-width="1"/>'
        )
        shown = value
        is_clipped = len(shown) > max_chars
        if is_clipped:
            shown = shown[: max(1, max_chars - 1)] + "…"
        nodes.append(
            f'<text x="{x + 4}" y="{y + min(17, cell_h - 5)}" font-family="monospace" font-size="11">{_xml_text(shown)}</text>'
        )
        if refs:
            serialized.update(refs)
            visible.update(refs)
            if is_clipped:
                clipped.update(refs)
            elements.append(
                PreviewElement(refs, float(x), float(y), float(cell_w), float(cell_h), "cell", is_clipped)
            )
    nodes.append("</svg>")
    return SvgPreview(
        ("\n".join(nodes) + "\n").encode("utf-8"),
        tuple(elements),
        tuple(sorted(serialized)),
        tuple(sorted(visible)),
        tuple(sorted(clipped)),
        (),
    )


def svg_text_page(
    *,
    title: str,
    lines: list[str],
    width: int = 794,
    height: int = 1123,
    font_size: int = 14,
    line_height: int = 20,
    margin: int = 48,
    footer: str | None = None,
) -> bytes:
    """Compatibility wrapper returning the first safely paginated SVG page."""
    items = [PreviewItem((), line, "text") for line in lines]
    pages = paginate_text_preview(
        title=title,
        items=items,
        width=width,
        height=height,
        font_size=font_size,
        line_height=line_height,
        margin=margin,
        footer=footer,
    )
    return pages[0].payload
