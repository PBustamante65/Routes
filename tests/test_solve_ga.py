import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import solve_ga as ga
import vrp_common as vc

NUM_STOPS = 6
NUM_TRUCKS = 2
SMALL_CAPACITY_CBM = 2.7
STOP_ROWS = list(range(2, 2 + NUM_STOPS))


def uniform_time_matrix(seconds=100):
    n = 2 + NUM_STOPS
    matrix = np.full((n, n), seconds)
    np.fill_diagonal(matrix, 0)
    return matrix


@pytest.fixture(scope="module")
def toy_routes():
    """6 stops, trucks that fill after 3 stops (2.7 cbm / 0.9 per stop)."""
    time_matrix = uniform_time_matrix()
    distance_matrix = time_matrix * 10.0
    return ga.solve(
        time_matrix,
        distance_matrix,
        NUM_STOPS,
        NUM_TRUCKS,
        time_limit_seconds=2,
        capacity_cbm=SMALL_CAPACITY_CBM,
        population_size=20,
        seed=0,
    )


def test_every_stop_visited_exactly_once(toy_routes):
    visited = [row for rows in toy_routes for row in rows if row != vc.LANDFILL_ROW]
    assert sorted(visited) == STOP_ROWS


def test_load_never_exceeds_capacity(toy_routes):
    for rows in toy_routes:
        load = 0.0
        for row in rows:
            if row == vc.LANDFILL_ROW:
                load = 0.0
            else:
                load += vc.STOP_DEMAND_CBM
            assert load <= SMALL_CAPACITY_CBM + 1e-9


def test_routes_respect_shift_cap(toy_routes):
    time_matrix = uniform_time_matrix()
    distance_matrix = time_matrix * 10.0
    for rows in toy_routes:
        summary = vc.summarize_route(rows, time_matrix, distance_matrix)
        assert summary["total_seconds"] <= vc.SHIFT_CAP_SECONDS


def test_decode_assigns_every_stop_to_exactly_one_truck():
    time_matrix = uniform_time_matrix()
    distance_matrix = time_matrix * 10.0
    chromosome = STOP_ROWS[:]
    random.Random(1).shuffle(chromosome)

    trucks_stops = ga.decode(
        chromosome, time_matrix, distance_matrix, NUM_TRUCKS, SMALL_CAPACITY_CBM, vc.SHIFT_CAP_SECONDS
    )

    assert len(trucks_stops) == NUM_TRUCKS
    assigned = sorted(stop for stops in trucks_stops for stop in stops)
    assert assigned == STOP_ROWS


def test_order_crossover_yields_a_valid_permutation():
    rng = random.Random(2)
    parent_a = STOP_ROWS[:]
    parent_b = STOP_ROWS[::-1]

    child = ga.order_crossover(rng, parent_a, parent_b)

    assert sorted(child) == STOP_ROWS


def test_swap_mutation_preserves_permutation():
    rng = random.Random(3)
    chromosome = STOP_ROWS[:]

    mutated = ga.swap_mutation(rng, chromosome, mutation_rate=1.0)

    assert sorted(mutated) == STOP_ROWS
    assert mutated != chromosome


def test_fitness_penalizes_shift_cap_violation():
    time_matrix = uniform_time_matrix(seconds=10000)
    distance_matrix = time_matrix * 10.0
    chromosome = STOP_ROWS[:]

    cost = ga.fitness(
        chromosome, time_matrix, distance_matrix, NUM_TRUCKS, SMALL_CAPACITY_CBM, vc.SHIFT_CAP_SECONDS
    )
    trucks_stops = ga.decode(
        chromosome, time_matrix, distance_matrix, NUM_TRUCKS, SMALL_CAPACITY_CBM, vc.SHIFT_CAP_SECONDS
    )
    uncapped_total = sum(
        vc.summarize_route(vc.insert_dumps(stops, SMALL_CAPACITY_CBM), time_matrix, distance_matrix)[
            "total_seconds"
        ]
        for stops in trucks_stops
    )

    assert cost > uncapped_total


def test_infeasible_shift_cap_raises():
    time_matrix = uniform_time_matrix()
    distance_matrix = time_matrix * 10.0
    with pytest.raises(RuntimeError):
        ga.solve(
            time_matrix,
            distance_matrix,
            NUM_STOPS,
            NUM_TRUCKS,
            time_limit_seconds=1,
            population_size=10,
            shift_cap_seconds=60,
            seed=0,
        )
