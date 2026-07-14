import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import vrp_common as vc


def test_insert_dumps_never_exceeds_capacity():
    stop_rows = [2, 3, 4, 5, 6, 7]
    rows = vc.insert_dumps(stop_rows, capacity_cbm=2.7, stop_demand_cbm=0.9)

    load = 0.0
    for row in rows:
        if row == vc.LANDFILL_ROW:
            load = 0.0
        else:
            load += 0.9
        assert load <= 2.7 + 1e-9


def test_insert_dumps_places_landfill_right_before_capacity_break():
    rows = vc.insert_dumps([2, 3, 4, 5], capacity_cbm=2.7, stop_demand_cbm=0.9)
    assert rows == [2, 3, 4, vc.LANDFILL_ROW, 5, vc.LANDFILL_ROW]


def test_insert_dumps_no_trailing_dump_when_empty():
    assert vc.insert_dumps([], capacity_cbm=2.7, stop_demand_cbm=0.9) == []


def test_insert_dumps_appends_final_dump_even_at_exact_capacity():
    rows = vc.insert_dumps([2, 3, 4], capacity_cbm=2.7, stop_demand_cbm=0.9)
    assert rows == [2, 3, 4, vc.LANDFILL_ROW]
