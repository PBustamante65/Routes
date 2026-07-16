"""
Sequential (coordinate-wise) grid search over the GA's hyperparameters,
run against the real problem instance (Data/points-index.csv + matrices).

A full factorial search across all five knobs (nn_seed_fraction,
two_opt_max_passes, population_size, mutation_rate, tournament_k) would
need hundreds of full-time-budget solves. Instead this tunes
nn_seed_fraction x two_opt_max_passes first (the two knobs this search
was built for), then re-tunes population_size x mutation_rate x
tournament_k holding stage 1's winner fixed -- far fewer trials, at the
cost of not exploring interactions across the two stages.

Usage:
    python3 tune_ga.py [--time-limit 60] [--seed 0]
        [--trials-out Data/ga-tuning-trials.csv]
"""

import argparse
import itertools
import time

import pandas as pd

import solve_ga
from benchmark_solvers import aggregate
from vrp_common import NUM_TRUCKS, load_data

STAGE_1_GRID = {
    "nn_seed_fraction": [0.0, 0.25, 0.5, 0.75, 1.0],
    "two_opt_max_passes": [0, 1, 2, 3],
}

STAGE_2_GRID = {
    "population_size": [60, 100, 150],
    "mutation_rate": [0.05, 0.15, 0.25],
    "tournament_k": [3, 4, 5],
}

DEFAULT_PARAMS = {
    "population_size": 100,
    "mutation_rate": 0.15,
    "tournament_k": 4,
    "nn_seed_fraction": 0.5,
    "two_opt_max_passes": 2,
}


def grid_combinations(grid):
    """Cartesian product of a {param_name: [values, ...]} grid, one dict
    per combination, in the order itertools.product visits them."""
    keys = list(grid)
    for values in itertools.product(*(grid[key] for key in keys)):
        yield dict(zip(keys, values))


def evaluate(params, time_matrix, distance_matrix, num_stops, time_limit_seconds, seed):
    start = time.monotonic()
    routes = solve_ga.solve(
        time_matrix,
        distance_matrix,
        num_stops,
        NUM_TRUCKS,
        time_limit_seconds,
        seed=seed,
        **params,
    )
    wall_seconds = time.monotonic() - start
    return {**aggregate(routes, time_matrix, distance_matrix), "wall_seconds": wall_seconds}


def run_stage(
    name, grid, base_params, time_matrix, distance_matrix, num_stops, time_limit_seconds, seed, trials
):
    """Evaluates every combination in grid (merged over base_params),
    appends one row per trial to trials, and returns the (params, result)
    of the combo with the lowest total_seconds."""
    combos = list(grid_combinations(grid))
    print(f"\n--- {name}: {len(combos)} combinaciones ---")
    best_params, best_result = None, None
    for overrides in combos:
        params = {**base_params, **overrides}
        result = evaluate(params, time_matrix, distance_matrix, num_stops, time_limit_seconds, seed)
        trials.append({"stage": name, **params, **result})
        hours, rem = divmod(result["total_seconds"], 3600)
        print(
            f"{overrides} -> {hours}h{rem // 60:02d}m, "
            f"{result['total_meters'] / 1000:.1f} km, {result['trucks_used']} camiones"
        )
        if best_result is None or result["total_seconds"] < best_result["total_seconds"]:
            best_params, best_result = params, result
    return best_params, best_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--time-limit", type=int, default=60, help="segundos de busqueda por combinacion"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--trials-out", default="Data/ga-tuning-trials.csv")
    args = parser.parse_args()

    _, time_matrix, distance_matrix, num_stops = load_data()
    trials = []

    stage1_best, _ = run_stage(
        "stage1_nn_seed_and_2opt",
        STAGE_1_GRID,
        DEFAULT_PARAMS,
        time_matrix,
        distance_matrix,
        num_stops,
        args.time_limit,
        args.seed,
        trials,
    )
    stage2_best, stage2_result = run_stage(
        "stage2_population_mutation_tournament",
        STAGE_2_GRID,
        stage1_best,
        time_matrix,
        distance_matrix,
        num_stops,
        args.time_limit,
        args.seed,
        trials,
    )

    pd.DataFrame(trials).to_csv(args.trials_out, index=False)
    hours, rem = divmod(stage2_result["total_seconds"], 3600)
    print(f"\nMejor configuracion: {stage2_best}")
    print(
        f"Resultado: {hours}h{rem // 60:02d}m, {stage2_result['total_meters'] / 1000:.1f} km, "
        f"{stage2_result['trucks_used']} camiones"
    )
    print(f"Trials guardados en: {args.trials_out}")


if __name__ == "__main__":
    main()
