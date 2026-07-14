import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import benchmark_solvers as bs
import vrp_common as vc


def test_aggregate_sums_across_trucks_and_counts_used_trucks():
    time_matrix = np.array(
        [
            [0, 50, 100, 100],
            [50, 0, 60, 60],
            [100, 60, 0, 60],
            [100, 60, 60, 0],
        ]
    )
    distance_matrix = time_matrix * 10.0
    routes = [[2, vc.LANDFILL_ROW], [3, vc.LANDFILL_ROW], []]

    stats = bs.aggregate(routes, time_matrix, distance_matrix)

    expected = vc.summarize_route(routes[0], time_matrix, distance_matrix)
    expected_2 = vc.summarize_route(routes[1], time_matrix, distance_matrix)
    assert stats["total_seconds"] == expected["total_seconds"] + expected_2["total_seconds"]
    assert stats["total_meters"] == expected["total_meters"] + expected_2["total_meters"]
    assert stats["total_dumps"] == expected["dumps"] + expected_2["dumps"]
    assert stats["trucks_used"] == 2
