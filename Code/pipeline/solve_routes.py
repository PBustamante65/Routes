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

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from vrp_common import (
    DEPOT_ROW,
    DUMP_SERVICE_SECONDS,
    LANDFILL_ROW,
    NUM_TRUCKS,
    SHIFT_CAP_SECONDS,
    STOP_DEMAND_CBM,
    STOP_SERVICE_SECONDS,
    TRUCK_CAPACITY_CBM,
    load_data,
    report_solution,
    summarize_route,
)

SOLUTION_DST = "Data/routes-solution.csv"

# Demands are scaled to integer tenths of a cbm (OR-Tools needs integers).
DEMAND_SCALE = 10

class Solution:
    def __init__(self):
        pass


    def num_landfill_copies(self, num_stops, num_trucks, capacity_cbm=TRUCK_CAPACITY_CBM):
        """Minimum dumps needed to move all trash, plus one spare partial
        dump per truck (the forced empty-before-depot return)."""
        total_demand = num_stops * round(STOP_DEMAND_CBM * DEMAND_SCALE)
        capacity = round(capacity_cbm * DEMAND_SCALE)
        return math.ceil(total_demand / capacity) + num_trucks


    def node_to_row(self, node, k_landfill):
        """Maps a solver node to its matrix row: node 0 is the depot, nodes
        1..k are landfill copies, the rest are stops in matrix order."""
        if node == 0:
            return DEPOT_ROW
        if node <= k_landfill:
            return LANDFILL_ROW
        return node - k_landfill + 1


    def solve(
        self,
        time_matrix,
        num_stops,
        num_trucks,
        time_limit_seconds,
        shift_cap_seconds=SHIFT_CAP_SECONDS,
        capacity_cbm=TRUCK_CAPACITY_CBM,
    ):
        """Returns one list of visited matrix rows per truck (depot excluded)."""
        k_landfill = self.num_landfill_copies(num_stops, num_trucks, capacity_cbm)
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
            travel = time_matrix[self.node_to_row(from_node, k_landfill)][
                self.node_to_row(to_node, k_landfill)
            ]
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
        params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )
        params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
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
                    rows.append(self.node_to_row(node, k_landfill))
                index = solution.Value(routing.NextVar(index))
            routes.append(rows)
        return routes


    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--time-limit", type=int, default=60, help="segundos de busqueda"
        )
        args = parser.parse_args()

        points, time_matrix, distance_matrix, num_stops = load_data()
        print(
            f"Resolviendo: {num_stops} paradas, {NUM_TRUCKS} camiones, limite {args.time_limit}s..."
        )

        routes = self.solve(time_matrix, num_stops, NUM_TRUCKS, args.time_limit)
        report_solution(routes, points, time_matrix, distance_matrix, SOLUTION_DST)


if __name__ == "__main__":
    Solution().main()
