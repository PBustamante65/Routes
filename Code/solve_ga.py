"""
Genetic-algorithm solver for the same multi-trip trash-collection VRP as
solve_routes.py, for comparison against the OR-Tools baseline.

A chromosome is a permutation of stop rows (the "giant tour"). Decoding
walks the permutation and greedily closes a truck's route once adding the
next stop would push it over the shift cap, so route sequencing and
truck assignment are both driven by the same permutation instead of two
separate decisions. Landfill dumps are then inserted deterministically
(vrp_common.insert_dumps) since dumping is forced by capacity, not a
choice the GA needs to make.

Part of the initial population is seeded with nearest-neighbor-constructed
tours (refined by 2-opt) instead of pure random permutations, and 2-opt is
reapplied to the elites carried over each generation -- a memetic-GA touch
meant to improve on a purely random-init, no-local-search baseline.

Usage:
    python3 solve_ga.py [--time-limit 60] [--population 60] [--seed 0]
"""

import argparse
import random
import time

from vrp_common import (
    DEPOT_ROW,
    NUM_TRUCKS,
    SHIFT_CAP_SECONDS,
    TRUCK_CAPACITY_CBM,
    insert_dumps,
    load_data,
    report_solution,
    summarize_route,
)

SOLUTION_DST = "Data/routes-solution-ga.csv"

SHIFT_CAP_PENALTY_FACTOR = 100


def decode(chromosome, time_matrix, distance_matrix, num_trucks, capacity_cbm, shift_cap_seconds):
    """Splits a stop permutation into num_trucks stop-only sequences (no
    dumps yet), closing a truck's route once the next stop would exceed
    the shift cap. The last truck absorbs any remaining stops even if
    that pushes it over the cap; fitness penalizes that instead of
    decoding failing outright, so every chromosome decodes to something
    evaluable."""
    trucks_stops = [[] for _ in range(num_trucks)]
    truck_idx = 0
    for stop in chromosome:
        candidate = trucks_stops[truck_idx] + [stop]
        within_cap = (
            summarize_route(insert_dumps(candidate, capacity_cbm), time_matrix, distance_matrix)[
                "total_seconds"
            ]
            <= shift_cap_seconds
        )
        if within_cap or not trucks_stops[truck_idx] or truck_idx == num_trucks - 1:
            trucks_stops[truck_idx] = candidate
        else:
            truck_idx += 1
            trucks_stops[truck_idx] = [stop]
    return trucks_stops


def fitness(chromosome, time_matrix, distance_matrix, num_trucks, capacity_cbm, shift_cap_seconds):
    """Lower is better: total route time plus a heavy penalty for any
    truck left over the shift cap."""
    trucks_stops = decode(
        chromosome, time_matrix, distance_matrix, num_trucks, capacity_cbm, shift_cap_seconds
    )
    total_seconds = 0
    penalty = 0
    for stops in trucks_stops:
        summary = summarize_route(insert_dumps(stops, capacity_cbm), time_matrix, distance_matrix)
        total_seconds += summary["total_seconds"]
        if summary["total_seconds"] > shift_cap_seconds:
            penalty += (summary["total_seconds"] - shift_cap_seconds) * SHIFT_CAP_PENALTY_FACTOR
    return total_seconds + penalty


def order_crossover(rng, parent_a, parent_b):
    """OX1: keeps a random slice of parent_a, fills the rest in parent_b's
    order, so every stop appears exactly once in the child."""
    n = len(parent_a)
    i, j = sorted(rng.sample(range(n), 2))
    slice_ = parent_a[i : j + 1]
    slice_set = set(slice_)
    fill_values = [gene for gene in parent_b if gene not in slice_set]

    child = [None] * n
    child[i : j + 1] = slice_
    pos = 0
    for k in range(n):
        if child[k] is None:
            child[k] = fill_values[pos]
            pos += 1
    return child


def swap_mutation(rng, chromosome, mutation_rate):
    chromosome = list(chromosome)
    if rng.random() < mutation_rate:
        i, j = rng.sample(range(len(chromosome)), 2)
        chromosome[i], chromosome[j] = chromosome[j], chromosome[i]
    return chromosome


def nearest_neighbor_tour(time_matrix, stop_rows, start_row):
    """Greedy construction: repeatedly visits the closest unvisited stop to
    the current one, starting from start_row (which is itself not part of
    the returned tour -- e.g. the depot, or a random stop for diversity
    across several seeded individuals)."""
    remaining = set(stop_rows)
    tour = []
    current = start_row
    while remaining:
        next_stop = min(remaining, key=lambda row: time_matrix[current][row])
        tour.append(next_stop)
        remaining.remove(next_stop)
        current = next_stop
    return tour


def two_opt(chromosome, time_matrix, depot_row, max_passes=2):
    """First-improvement 2-opt over the giant tour depot -> chromosome ->
    depot, using time_matrix as the edge cost. This ignores the truck
    splits/capacity that the real fitness() accounts for, but is a cheap,
    standard proxy for tour quality (a memetic-GA local search over the
    full permutation, not per truck route). Capped at max_passes full
    sweeps since a sweep is O(n^2) and this runs every generation."""
    tour = [depot_row] + list(chromosome) + [depot_row]
    m = len(tour)
    for _ in range(max_passes):
        improved = False
        for i in range(1, m - 1):
            for j in range(i + 1, m - 1):
                a, b = tour[i - 1], tour[i]
                c, d = tour[j], tour[j + 1]
                delta = (
                    time_matrix[a][c] + time_matrix[b][d]
                    - time_matrix[a][b] - time_matrix[c][d]
                )
                if delta < -1e-9:
                    tour[i : j + 1] = tour[i : j + 1][::-1]
                    improved = True
        if not improved:
            break
    return tour[1:-1]


def tournament_select(rng, population, fitnesses, k):
    contenders = rng.sample(range(len(population)), k)
    best = min(contenders, key=lambda idx: fitnesses[idx])
    return population[best]


def solve(
    time_matrix,
    distance_matrix,
    num_stops,
    num_trucks,
    time_limit_seconds,
    capacity_cbm=TRUCK_CAPACITY_CBM,
    shift_cap_seconds=SHIFT_CAP_SECONDS,
    population_size=60,
    elite_size=4,
    mutation_rate=0.15,
    tournament_k=5,
    nn_seed_fraction=1.0,
    two_opt_max_passes=3,
    seed=None,
):
    """Returns one list of visited matrix rows per truck (depot excluded),
    same shape as solve_routes.solve."""
    rng = random.Random(seed)
    stop_rows = list(range(2, 2 + num_stops))

    def eval_fitness(chromosome):
        return fitness(
            chromosome, time_matrix, distance_matrix, num_trucks, capacity_cbm, shift_cap_seconds
        )

    def build_nn_individual():
        # Randomized start point so several NN-seeded individuals differ,
        # instead of all collapsing onto the single depot-start NN tour.
        start_row = rng.choice(stop_rows)
        tour = nearest_neighbor_tour(time_matrix, stop_rows, start_row)
        return two_opt(tour, time_matrix, DEPOT_ROW, max_passes=two_opt_max_passes)

    nn_count = round(population_size * nn_seed_fraction)
    population = [build_nn_individual() for _ in range(nn_count)]
    for _ in range(population_size - nn_count):
        individual = stop_rows[:]
        rng.shuffle(individual)
        population.append(individual)
    fitnesses = [eval_fitness(individual) for individual in population]

    best_idx = min(range(len(population)), key=lambda i: fitnesses[i])
    best_chromosome = population[best_idx][:]
    best_fitness = fitnesses[best_idx]

    start = time.monotonic()
    while time.monotonic() - start < time_limit_seconds:
        ranked = sorted(range(len(population)), key=lambda i: fitnesses[i])
        next_population = [
            two_opt(population[i], time_matrix, DEPOT_ROW, max_passes=two_opt_max_passes)
            for i in ranked[:elite_size]
        ]
        while len(next_population) < population_size:
            parent_a = tournament_select(rng, population, fitnesses, tournament_k)
            parent_b = tournament_select(rng, population, fitnesses, tournament_k)
            child = order_crossover(rng, parent_a, parent_b)
            child = swap_mutation(rng, child, mutation_rate)
            next_population.append(child)
        population = next_population
        fitnesses = [eval_fitness(individual) for individual in population]

        gen_best_idx = min(range(len(population)), key=lambda i: fitnesses[i])
        if fitnesses[gen_best_idx] < best_fitness:
            best_fitness = fitnesses[gen_best_idx]
            best_chromosome = population[gen_best_idx][:]

    trucks_stops = decode(
        best_chromosome, time_matrix, distance_matrix, num_trucks, capacity_cbm, shift_cap_seconds
    )
    routes = [insert_dumps(stops, capacity_cbm) for stops in trucks_stops]

    for rows in routes:
        if summarize_route(rows, time_matrix, distance_matrix)["total_seconds"] > shift_cap_seconds:
            raise RuntimeError(
                "No se encontro solucion factible dentro del limite de tiempo "
                "(aumenta --time-limit o --population)."
            )
    return routes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--time-limit", type=int, default=60, help="segundos de busqueda")
    parser.add_argument("--population", type=int, default=60, help="tamano de poblacion")
    parser.add_argument("--mutation-rate", type=float, default=0.15)
    parser.add_argument("--tournament-k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    points, time_matrix, distance_matrix, num_stops = load_data()
    print(
        f"Resolviendo (GA): {num_stops} paradas, {NUM_TRUCKS} camiones, "
        f"poblacion {args.population}, limite {args.time_limit}s..."
    )

    routes = solve(
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
    report_solution(routes, points, time_matrix, distance_matrix, SOLUTION_DST)


if __name__ == "__main__":
    main()
