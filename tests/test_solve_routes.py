import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import solve_routes as sr

NUM_STOPS = 6
NUM_TRUCKS = 2
SMALL_CAPACITY_CBM = 2.7


def uniform_time_matrix(seconds=100):
    n = 2 + NUM_STOPS
    matrix = np.full((n, n), seconds)
    np.fill_diagonal(matrix, 0)
    return matrix


@pytest.fixture(scope="module")
def toy_routes():
    """6 stops, trucks that fill after 3 stops (2.7 cbm / 0.9 per stop)."""
    return sr.solve(
        uniform_time_matrix(),
        NUM_STOPS,
        NUM_TRUCKS,
        time_limit_seconds=3,
        capacity_cbm=SMALL_CAPACITY_CBM,
    )


def test_num_landfill_copies_scales_with_data():
    assert sr.num_landfill_copies(218, 10) == 35
    assert sr.num_landfill_copies(8, 1) == 2
    assert sr.num_landfill_copies(300, 5) == 39


def test_node_to_row_mapping():
    k = 3
    assert sr.node_to_row(0, k) == 0
    assert all(sr.node_to_row(node, k) == 1 for node in (1, 2, 3))
    assert sr.node_to_row(4, k) == 2
    assert sr.node_to_row(5, k) == 3


def test_every_stop_visited_exactly_once(toy_routes):
    visited = [row for rows in toy_routes for row in rows if row != sr.LANDFILL_ROW]
    assert sorted(visited) == list(range(2, 2 + NUM_STOPS))


def test_load_never_exceeds_capacity(toy_routes):
    for rows in toy_routes:
        load = 0.0
        for row in rows:
            if row == sr.LANDFILL_ROW:
                load = 0.0
            else:
                load += sr.STOP_DEMAND_CBM
            assert load <= SMALL_CAPACITY_CBM + 1e-9


def test_trucks_dump_before_returning_to_depot(toy_routes):
    for rows in toy_routes:
        if any(row != sr.LANDFILL_ROW for row in rows):
            assert rows[-1] == sr.LANDFILL_ROW


def test_enough_dumps_for_total_demand(toy_routes):
    dumps = sum(row == sr.LANDFILL_ROW for rows in toy_routes for row in rows)
    assert dumps >= 2


def test_routes_respect_shift_cap(toy_routes):
    time_matrix = uniform_time_matrix()
    distance_matrix = time_matrix * 10.0
    for rows in toy_routes:
        summary = sr.summarize_route(rows, time_matrix, distance_matrix)
        assert summary["total_seconds"] <= sr.SHIFT_CAP_SECONDS


def test_summarize_route_accumulates_time_load_and_dumps():
    time_matrix = np.array(
        [
            [0, 50, 100],
            [50, 0, 60],
            [100, 60, 0],
        ]
    )
    distance_matrix = time_matrix * 10.0

    summary = sr.summarize_route([2, 1], time_matrix, distance_matrix)

    assert summary["stops"] == 1
    assert summary["dumps"] == 1
    assert summary["visits"][0]["arrival_seconds"] == 100
    assert summary["visits"][0]["load_after_cbm"] == sr.STOP_DEMAND_CBM
    assert summary["visits"][1]["arrival_seconds"] == 100 + sr.STOP_SERVICE_SECONDS + 60
    assert summary["visits"][1]["load_after_cbm"] == 0.0
    expected_total = 100 + sr.STOP_SERVICE_SECONDS + 60 + sr.DUMP_SERVICE_SECONDS + 50
    assert summary["total_seconds"] == expected_total
    assert summary["total_meters"] == (100 + 60 + 50) * 10.0


def test_empty_route_summary_is_zeroed():
    time_matrix = uniform_time_matrix()
    summary = sr.summarize_route([], time_matrix, time_matrix * 10.0)
    assert summary["stops"] == 0
    assert summary["dumps"] == 0
    assert summary["total_seconds"] == 0
    assert summary["total_meters"] == 0.0


def test_infeasible_shift_cap_raises():
    with pytest.raises(RuntimeError):
        sr.solve(
            uniform_time_matrix(),
            NUM_STOPS,
            NUM_TRUCKS,
            time_limit_seconds=2,
            shift_cap_seconds=60,
        )
