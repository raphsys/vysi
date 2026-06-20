from __future__ import annotations

from vysi.document_source.rendering_v2.v082.grid import occupied_tiles


def test_sparse_tiles_only_cover_occupied_regions() -> None:
    records = [
        ("cell_a", 0, 0, "a"),
        ("cell_b", 1_048_575, 16_383, "b"),
    ]
    tiles = occupied_tiles(records)
    assert len(tiles) == 2
    assert (0, 0) in tiles
    assert (40_329, 1_365) in tiles
