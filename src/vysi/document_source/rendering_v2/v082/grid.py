from __future__ import annotations

from collections import defaultdict

MAX_ROWS = 26
MAX_COLUMNS = 12
GridCell = tuple[str, int, int, str]


def occupied_tiles(records: list[GridCell]) -> dict[tuple[int, int], list[GridCell]]:
    buckets: dict[tuple[int, int], list[GridCell]] = defaultdict(list)
    for cell_id, row, column, value in records:
        key = (row // MAX_ROWS, column // MAX_COLUMNS)
        buckets[key].append((cell_id, row, column, value))
    return dict(sorted(buckets.items()))
