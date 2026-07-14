"""
Solves the multi-trip trash-collection VRP: assigns Oxxo stops to trucks
and orders each route, inserting landfill dump visits whenever a truck
fills up, minimizing total route time (travel + service + disposal).

OR-Tools' routing model visits each node at most once, so the landfill is
duplicated into optional "reload" copies (the documented reload idiom);
the copy count is derived from total demand, never hardcoded.

Usage:
    python3 solve_routes.py [--time-limit 60]
"""

import argparse
import math

import numpy as np
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

POINTS_INDEX_SRC = "Data/points-index.csv"
TIME_MATRIX_SRC = "Data/time-matrix-seconds.csv"
DISTANCE_MATRIX_SRC = "Data/distance-matrix-meters.csv"
SOLUTION_DST = "Data/routes-solution.csv"

NUM_TRUCKS = 10
TRUCK_CAPACITY_CBM = 8.0
STOP_DEMAND_CBM = 0.9
STOP_SERVICE_SECONDS = 180
DUMP_SERVICE_SECONDS = 900
SHIFT_CAP_SECONDS = 8 * 3600

# Demands are scaled to integer tenths of a cbm (OR-Tools needs integers).
DEMAND_SCALE = 10

DEPOT_ROW = 0
LANDFILL_ROW = 1


def num_landfill_copies(num_stops, num_trucks, capacity_cbm=TRUCK_CAPACITY_CBM):
    """Minimum dumps needed to move all trash, plus one spare partial
    dump per truck (the forced empty-before-depot return)."""
    total_demand = num_stops * round(STOP_DEMAND_CBM * DEMAND_SCALE)
    capacity = round(capacity_cbm * DEMAND_SCALE)
    return math.ceil(total_demand / capacity) + num_trucks


def node_to_row(node, k_landfill):
    """Maps a solver node to its matrix row: node 0 is the depot, nodes
    1..k are landfill copies, the rest are stops in matrix order."""
    if node == 0:
        return DEPOT_ROW
    if node <= k_landfill:
        return LANDFILL_ROW
    return node - k_landfill + 1


def solve(
    time_matrix,
    num_stops,
    num_trucks,
    time_limit_seconds,
    shift_cap_seconds=SHIFT_CAP_SECONDS,
    capacity_cbm=TRUCK_CAPACITY_CBM,
):
    """Returns one list of visited matrix rows per truck (depot excluded)."""
    k_landfill = num_landfill_copies(num_stops, num_trucks, capacity_cbm)
    num_nodes = 1 + k_landfill + num_stops

    stop_demand = round(STOP_DEMAND_CBM * DEMAND_SCALE)
    capacity = round(capacity_cbm * DEMAND_SCALE)

    manager = pywrapcp.RoutingIndexManager(num_nodes, num_trucks, 0)
    routing = pywrapcp.RoutingModel(manager)

    def is_landfill(node):
        return 1 <= node <= k_landfill

    def time_transit(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel = time_matrix[node_to_row(from_node, k_landfill)][node_to_row(to_node, k_landfill)]
        if is_landfill(from_node):
            service = DUMP_SERVICE_SECONDS
        elif from_node == 0:
            service = 0
        else:
            service = STOP_SERVICE_SECONDS
        return int(travel) + service

    transit_cb = routing.RegisterTransitCallback(time_transit)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    routing.AddDimension(transit_cb, 0, shift_cap_seconds, True, "Time")

    def demand_transit(from_index):
        node = manager.IndexToNode(from_index)
        if node == 0:
            return 0
        if is_landfill(node):
            return -capacity
        return stop_demand

    demand_cb = routing.RegisterUnaryTransitCallback(demand_transit)
    # Slack lets the load drop to exactly zero at a dump instead of going
    # negative when the truck arrives with a partial load; it is pinned to
    # zero everywhere else so loads only change by each node's demand.
    routing.AddDimension(demand_cb, capacity, capacity, True, "Load")
    load_dim = routing.GetDimensionOrDie("Load")
    for node in range(1, num_nodes):
        if not is_landfill(node):
            load_dim.SlackVar(manager.NodeToIndex(node)).SetValue(0)
    for vehicle in range(num_trucks):
        load_dim.SlackVar(routing.Start(vehicle)).SetValue(0)
        routing.solver().Add(load_dim.CumulVar(routing.End(vehicle)) == 0)

    for node in range(1, k_landfill + 1):
        routing.AddDisjunction([manager.NodeToIndex(node)], 0)

    params = pywrapcp.DefaultRoutingSearchParameters()
    # Path-building strategies (PATH_CHEAPEST_ARC, SAVINGS) fail to find any
    # feasible first solution under the hard shift cap plus the empty-at-depot
    # constraint; insertion handles side constraints while constructing.
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromSeconds(time_limit_seconds)

    solution = routing.SolveWithParameters(params)
    if solution is None:
        raise RuntimeError("No se encontro solucion factible (revisa capacidad/turno).")

    routes = []
    for vehicle in range(num_trucks):
        rows = []
        index = routing.Start(vehicle)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                rows.append(node_to_row(node, k_landfill))
            index = solution.Value(routing.NextVar(index))
        routes.append(rows)
    return routes


def summarize_route(rows, time_matrix, distance_matrix):
    """Walks one route (matrix rows, depot excluded) and returns totals
    plus per-visit arrival time and load."""
    visits = []
    load_cbm = 0.0
    clock = 0
    distance = 0.0
    prev = DEPOT_ROW
    stops = 0
    dumps = 0

    for row in rows:
        clock += int(time_matrix[prev][row])
        distance += distance_matrix[prev][row]
        if row == LANDFILL_ROW:
            dumps += 1
            load_cbm = 0.0
            service = DUMP_SERVICE_SECONDS
        else:
            stops += 1
            load_cbm += STOP_DEMAND_CBM
            service = STOP_SERVICE_SECONDS
        visits.append({"row": row, "arrival_seconds": clock, "load_after_cbm": round(load_cbm, 1)})
        clock += service
        prev = row

    clock += int(time_matrix[prev][DEPOT_ROW]) if rows else 0
    distance += distance_matrix[prev][DEPOT_ROW] if rows else 0.0

    return {
        "visits": visits,
        "stops": stops,
        "dumps": dumps,
        "total_seconds": clock,
        "total_meters": distance,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--time-limit", type=int, default=60, help="segundos de busqueda")
    args = parser.parse_args()

    points = pd.read_csv(POINTS_INDEX_SRC)
    time_matrix = pd.read_csv(TIME_MATRIX_SRC, index_col=0).to_numpy()
    distance_matrix = pd.read_csv(DISTANCE_MATRIX_SRC, index_col=0).to_numpy()

    num_stops = len(points) - 2
    print(f"Resolviendo: {num_stops} paradas, {NUM_TRUCKS} camiones, limite {args.time_limit}s...")

    routes = solve(time_matrix, num_stops, NUM_TRUCKS, args.time_limit)

    records = []
    total_seconds = 0
    total_meters = 0.0
    total_dumps = 0
    for truck, rows in enumerate(routes):
        summary = summarize_route(rows, time_matrix, distance_matrix)
        total_seconds += summary["total_seconds"]
        total_meters += summary["total_meters"]
        total_dumps += summary["dumps"]
        for seq, visit in enumerate(summary["visits"]):
            point = points.iloc[visit["row"]]
            records.append(
                {
                    "truck": truck,
                    "seq": seq,
                    "id": point["id"],
                    "tienda": point["tienda"],
                    "tipo": point["tipo"],
                    "arrival_seconds": visit["arrival_seconds"],
                    "load_after_cbm": visit["load_after_cbm"],
                }
            )
        hours, rem = divmod(summary["total_seconds"], 3600)
        print(
            f"Camion {truck}: {summary['stops']} paradas, {summary['dumps']} viajes al relleno, "
            f"{hours}h{rem // 60:02d}m, {summary['total_meters'] / 1000:.1f} km"
        )

    pd.DataFrame(records).to_csv(SOLUTION_DST, index=False)
    hours, rem = divmod(total_seconds, 3600)
    print(
        f"\nTotal: {hours}h{rem // 60:02d}m, {total_meters / 1000:.1f} km, "
        f"{total_dumps} viajes al relleno"
    )
    print(f"Solucion guardada en: {SOLUTION_DST}")


if __name__ == "__main__":
    main()
