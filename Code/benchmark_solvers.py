"""
Runs the OR-Tools and GA solvers on the same VRP instance with the same
time budget each, and prints a comparison table.

Usage:
    python3 benchmark_solvers.py [--time-limit 60] [--population 60]
        [--mutation-rate 0.15] [--tournament-k 5] [--seed 0]
"""

import argparse
import time

import solve_ga
import solve_routes
from vrp_common import NUM_TRUCKS, load_data, report_solution, summarize_route


def aggregate(routes, time_matrix, distance_matrix):
    total_seconds = 0
    total_meters = 0.0
    total_dumps = 0
    trucks_used = 0
    for rows in routes:
        summary = summarize_route(rows, time_matrix, distance_matrix)
        total_seconds += summary["total_seconds"]
        total_meters += summary["total_meters"]
        total_dumps += summary["dumps"]
        if summary["stops"] > 0:
            trucks_used += 1
    return {
        "total_seconds": total_seconds,
        "total_meters": total_meters,
        "total_dumps": total_dumps,
        "trucks_used": trucks_used,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--time-limit", type=int, default=60, help="segundos de busqueda por solver")
    parser.add_argument("--population", type=int, default=60, help="tamano de poblacion (GA)")
    parser.add_argument("--mutation-rate", type=float, default=0.15, help="tasa de mutacion (GA)")
    parser.add_argument("--tournament-k", type=int, default=5, help="tamano de torneo (GA)")
    parser.add_argument("--seed", type=int, default=0, help="semilla del GA")
    args = parser.parse_args()

    points, time_matrix, distance_matrix, num_stops = load_data()
    print(f"Comparando solvers: {num_stops} paradas, {NUM_TRUCKS} camiones, limite {args.time_limit}s c/u\n")

    results = {}

    print("--- OR-Tools ---")
    start = time.monotonic()
    ortools_routes = solve_routes.solve(time_matrix, num_stops, NUM_TRUCKS, args.time_limit)
    ortools_wall_seconds = time.monotonic() - start
    report_solution(ortools_routes, points, time_matrix, distance_matrix, solve_routes.SOLUTION_DST)
    results["OR-Tools"] = {
        **aggregate(ortools_routes, time_matrix, distance_matrix),
        "wall_seconds": ortools_wall_seconds,
    }

    print("\n--- GA ---")
    start = time.monotonic()
    ga_routes = solve_ga.solve(
        time_matrix,
        distance_matrix,
        num_stops,
        NUM_TRUCKS,
        args.time_limit,
        population_size=args.population,
        mutation_rate=args.mutation_rate,
        tournament_k=args.tournament_k,
        seed=args.seed,
    )
    ga_wall_seconds = time.monotonic() - start
    report_solution(ga_routes, points, time_matrix, distance_matrix, solve_ga.SOLUTION_DST)
    results["GA"] = {
        **aggregate(ga_routes, time_matrix, distance_matrix),
        "wall_seconds": ga_wall_seconds,
    }

    print("\n--- Comparacion ---")
    header = f"{'Solver':<10} {'Tiempo total':>14} {'Distancia':>12} {'Camiones':>10} {'Rellenos':>10} {'Computo':>10}"
    print(header)
    for name, stats in results.items():
        hours, rem = divmod(stats["total_seconds"], 3600)
        time_label = f"{hours}h{rem // 60:02d}m"
        distance_label = f"{stats['total_meters'] / 1000:.1f} km"
        wall_label = f"{stats['wall_seconds']:.1f}s"
        print(
            f"{name:<10} {time_label:>14} {distance_label:>12} "
            f"{stats['trucks_used']:>10} {stats['total_dumps']:>10} {wall_label:>10}"
        )


if __name__ == "__main__":
    main()
