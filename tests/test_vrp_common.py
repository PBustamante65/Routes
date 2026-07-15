import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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


@pytest.fixture
def toy_points():
    return pd.DataFrame(
        {
            "id": ["DEPOT::D", "LANDFILL::L", "STOP::A", "STOP::B"],
            "tienda": ["D", "L", "A", "B"],
            "tipo": ["DEPOT", "LANDFILL", "STOP", "STOP"],
        }
    )


def test_report_solution_writes_per_truck_summary(tmp_path, toy_points):
    time_matrix = np.array(
        [
            [0, 50, 100, 120],
            [50, 0, 60, 80],
            [100, 60, 0, 40],
            [120, 80, 40, 0],
        ]
    )
    distance_matrix = time_matrix * 10.0
    routes = [[2, 3, 1], []]
    dst_path = str(tmp_path / "routes-solution.csv")

    totals = vc.report_solution(routes, toy_points, time_matrix, distance_matrix, dst_path)

    summary = pd.read_csv(str(tmp_path / "routes-solution-summary.csv"))
    assert list(summary["truck"]) == [0]
    assert summary["stops"].iloc[0] == 2
    assert summary["dumps"].iloc[0] == 1
    assert summary["total_seconds"].iloc[0] == totals["summaries"][0]["total_seconds"]
    assert summary["total_meters"].iloc[0] == totals["summaries"][0]["total_meters"]
