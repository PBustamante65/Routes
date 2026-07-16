import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import tune_ga

NUM_STOPS = 6


def uniform_time_matrix(seconds=100):
    n = 2 + NUM_STOPS
    matrix = np.full((n, n), seconds)
    np.fill_diagonal(matrix, 0)
    return matrix


def test_grid_combinations_yields_cartesian_product():
    grid = {"a": [1, 2], "b": [3, 4]}

    combos = list(tune_ga.grid_combinations(grid))

    assert combos == [
        {"a": 1, "b": 3},
        {"a": 1, "b": 4},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
    ]


def test_evaluate_returns_aggregate_stats_and_wall_time():
    time_matrix = uniform_time_matrix()
    distance_matrix = time_matrix * 10.0

    result = tune_ga.evaluate(
        {"population_size": 10, "nn_seed_fraction": 0.5, "two_opt_max_passes": 1},
        time_matrix,
        distance_matrix,
        NUM_STOPS,
        time_limit_seconds=1,
        seed=0,
    )

    assert result["trucks_used"] > 0
    assert result["total_seconds"] > 0
    assert result["wall_seconds"] >= 0


def test_run_stage_picks_the_lowest_total_seconds_combo():
    time_matrix = uniform_time_matrix()
    distance_matrix = time_matrix * 10.0
    trials = []

    base_params = {
        "nn_seed_fraction": 0.5,
        "two_opt_max_passes": 1,
        "mutation_rate": 0.15,
        "tournament_k": 2,
    }

    best_params, best_result = tune_ga.run_stage(
        "test_stage",
        {"population_size": [10, 20]},
        base_params,
        time_matrix,
        distance_matrix,
        NUM_STOPS,
        time_limit_seconds=1,
        seed=0,
        trials=trials,
    )

    assert best_params["population_size"] in (10, 20)
    assert len(trials) == 2
    assert all(t["stage"] == "test_stage" for t in trials)
    assert best_result["total_seconds"] == min(t["total_seconds"] for t in trials)
