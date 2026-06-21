from __future__ import annotations

from vysi.document_source.rendering_v2.v082.grid import occupied_tiles
from vysi.document_source.rendering_v2.v082.text import word_items


def test_sparse_tiles_only_cover_occupied_regions() -> None:
    records = [
        ("cell_a", 0, 0, "a"),
        ("cell_b", 1_048_575, 16_383, "b"),
    ]
    tiles = occupied_tiles(records)
    assert len(tiles) == 2
    assert (0, 0) in tiles
    assert (40_329, 1_365) in tiles


def test_word_items_preserve_source_order() -> None:
    profile = {
        "blocks": [
            {"unit_id": "first", "kind": "paragraph", "text": "first"},
            {"unit_id": "cell", "kind": "cell", "text": "cell"},
            {"unit_id": "inside", "kind": "paragraph", "parent_id": "cell", "text": "cell"},
            {"unit_id": "last", "kind": "paragraph", "text": "last"},
        ]
    }
    items, refs = word_items(profile)
    assert [item.text for item in items] == ["first", "cell", "last"]
    assert [item.refs[0] for item in items] == ["first", "inside", "last"]
    assert "cell" not in refs
