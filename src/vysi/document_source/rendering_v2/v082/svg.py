from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


@dataclass(frozen=True)
class Item:
    refs: tuple[str, ...]
    text: str
    role: str = "text"


@dataclass(frozen=True)
class Element:
    refs: tuple[str, ...]
    x: float
    y: float
    width: float
    height: float
    role: str
    clipped: bool = False


@dataclass(frozen=True)
class Preview:
    payload: bytes
    elements: tuple[Element, ...]
    serialized: tuple[str, ...]
    visible: tuple[str, ...]
    clipped: tuple[str, ...]
    omitted: tuple[str, ...] = ()


def _text(parent: ET.Element, x: float, y: float, value: str, size: int, **attrs: str) -> None:
    node = ET.SubElement(
        parent,
        f"{{{SVG_NS}}}text",
        {"x": str(x), "y": str(y), "font-family": "monospace", "font-size": str(size), **attrs},
    )
    node.text = "".join(c if c in "\t\n\r" or ord(c) >= 32 else "�" for c in value)


def _segments(value: str, width: int) -> Iterable[str]:
    for line in value.expandtabs(4).splitlines() or [value.expandtabs(4)]:
        if not line:
            yield "[empty]"
            continue
        yield from textwrap.wrap(
            line,
            width=max(1, width),
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        ) or ["[empty]"]


def text_pages(
    *,
    title: str,
    items: list[Item],
    width: int,
    height: int,
    footer: str,
    check: Callable[[], None],
    font_size: int = 14,
    line_height: int = 20,
    margin: int = 48,
) -> list[Preview]:
    usable = max(1, width - 2 * margin)
    max_chars = max(1, int(usable / (font_size * 0.68)))
    first_y = margin + 34
    capacity = max(1, (height - first_y - margin - 34) // line_height)
    pages: list[Preview] = []
    chunk: list[tuple[Item, str]] = []
    seen = 0

    def flush() -> None:
        nonlocal chunk
        if not chunk:
            return
        root = ET.Element(
            f"{{{SVG_NS}}}svg",
            {"width": str(width), "height": str(height), "viewBox": f"0 0 {width} {height}"},
        )
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}rect",
            {"x": "0", "y": "0", "width": "100%", "height": "100%", "fill": "white"},
        )
        _text(root, margin, margin, f"{title} - {len(pages) + 1}", 16, **{"font-weight": "bold"})
        y = first_y
        elements: list[Element] = []
        serialized: set[str] = set()
        visible: set[str] = set()
        for item, segment in chunk:
            _text(root, margin, y, segment, font_size, **{"xml:space": "preserve"})
            if item.refs:
                serialized.update(item.refs)
                visible.update(item.refs)
                elements.append(
                    Element(
                        item.refs,
                        float(margin),
                        float(y - font_size),
                        float(min(usable, max(font_size * 0.68, len(segment) * font_size * 0.68))),
                        float(line_height),
                        item.role,
                    )
                )
            y += line_height
        _text(root, margin, height - 22, footer, 10)
        pages.append(
            Preview(
                ET.tostring(root, encoding="utf-8", xml_declaration=True),
                tuple(elements),
                tuple(sorted(serialized)),
                tuple(sorted(visible)),
                (),
            )
        )
        chunk = []

    for item in items:
        check()
        for segment in _segments(item.text, max_chars):
            seen += 1
            if seen % 64 == 0:
                check()
            chunk.append((item, segment))
            if len(chunk) >= capacity:
                flush()
    if not chunk and not pages:
        chunk.append((Item((), "[no renderable text]", "empty"), "[no renderable text]"))
    flush()
    return pages


def table_page(
    *,
    title: str,
    cells: list[tuple[tuple[str, ...], int, int, str]],
    check: Callable[[], None],
    width: int = 1123,
    height: int = 794,
    max_rows: int = 26,
    max_columns: int = 12,
) -> Preview:
    left, top = 36, 70
    columns = max(1, min(max((c for _, _, c, _ in cells), default=0) + 1, max_columns))
    rows = max(1, min(max((r for _, r, _, _ in cells), default=0) + 1, max_rows))
    cell_w = max(65, (width - 2 * left) // columns)
    cell_h = max(22, min(30, (height - top - 30) // rows))
    max_chars = max(1, int((cell_w - 8) / (11 * 0.68)))
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {"width": str(width), "height": str(height), "viewBox": f"0 0 {width} {height}"},
    )
    ET.SubElement(
        root,
        f"{{{SVG_NS}}}rect",
        {"x": "0", "y": "0", "width": "100%", "height": "100%", "fill": "white"},
    )
    _text(root, left, 36, title, 18, **{"font-weight": "bold"})
    elements: list[Element] = []
    serialized: set[str] = set()
    visible: set[str] = set()
    clipped: set[str] = set()
    for index, (refs, row, col, value) in enumerate(cells):
        if index % 64 == 0:
            check()
        if row >= rows or col >= columns:
            continue
        x, y = left + col * cell_w, top + row * cell_h
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}rect",
            {
                "x": str(x),
                "y": str(y),
                "width": str(cell_w),
                "height": str(cell_h),
                "fill": "none",
                "stroke": "#777",
                "stroke-width": "1",
            },
        )
        cut = len(value) > max_chars
        shown = value[: max(1, max_chars - 1)] + "..." if cut else value
        _text(root, x + 4, y + min(17, cell_h - 5), shown, 11)
        if refs:
            serialized.update(refs)
            visible.update(refs)
            if cut:
                clipped.update(refs)
            elements.append(
                Element(refs, float(x), float(y), float(cell_w), float(cell_h), "cell", cut)
            )
    return Preview(
        ET.tostring(root, encoding="utf-8", xml_declaration=True),
        tuple(elements),
        tuple(sorted(serialized)),
        tuple(sorted(visible)),
        tuple(sorted(clipped)),
    )
