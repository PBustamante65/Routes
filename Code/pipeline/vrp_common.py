"""
Shared data loading, route-costing, and reporting for the multi-trip
trash-collection VRP, used by every solver (OR-Tools, GA, ...) so they
stay comparable: same data, same cost definition, same output format.
"""

import pandas as pd

POINTS_INDEX_SRC = "Data/points-index.csv"
TIME_MATRIX_SRC = "Data/time-matrix-seconds.csv"
DISTANCE_MATRIX_SRC = "Data/distance-matrix-meters.csv"

NUM_TRUCKS = 10
TRUCK_CAPACITY_CBM = 8.0
STOP_DEMAND_CBM = 0.9
STOP_SERVICE_SECONDS = 180
DUMP_SERVICE_SECONDS = 900
SHIFT_CAP_SECONDS = 8 * 3600

DEPOT_ROW = 0
LANDFILL_ROW = 1


def load_data():
    """Returns (points, time_matrix, distance_matrix, num_stops)."""
    points = pd.read_csv(POINTS_INDEX_SRC)
    time_matrix = pd.read_csv(TIME_MATRIX_SRC, index_col=0).to_numpy()
    distance_matrix = pd.read_csv(DISTANCE_MATRIX_SRC, index_col=0).to_numpy()
    num_stops = len(points) - 2
    return points, time_matrix, distance_matrix, num_stops


def insert_dumps(stop_rows, capacity_cbm=TRUCK_CAPACITY_CBM, stop_demand_cbm=STOP_DEMAND_CBM):
    """Expands a truck's stop sequence (matrix rows, no dumps) into the
    full route: a landfill visit is inserted right before any stop that
    would push the load over capacity, and a final one if the truck still
    carries a load, since it must return to the depot empty."""
    rows = []
    load = 0.0
    for row in stop_rows:
        if load + stop_demand_cbm > capacity_cbm + 1e-9:
            rows.append(LANDFILL_ROW)
            load = 0.0
        rows.append(row)
        load += stop_demand_cbm
    if load > 1e-9:
        rows.append(LANDFILL_ROW)
    return rows


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
        visits.append(
            {"row": row, "arrival_seconds": clock, "load_after_cbm": round(load_cbm, 1)}
        )
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


def report_solution(routes, points, time_matrix, distance_matrix, dst_path, label="Camion"):
    """Prints a per-truck summary, writes the ordered solution to dst_path,
    and returns the aggregate totals plus each truck's summary dict."""
    records = []
    total_seconds = 0
    total_meters = 0.0
    total_dumps = 0
    summaries = []
    for truck, rows in enumerate(routes):
        summary = summarize_route(rows, time_matrix, distance_matrix)
        summaries.append(summary)
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
                    "meters": distance_matrix[visit["row"]][DEPOT_ROW],
                }
            )
        hours, rem = divmod(summary["total_seconds"], 3600)
        print(
            f"{label} {truck}: {summary['stops']} paradas, {summary['dumps']} viajes al relleno, "
            f"{hours}h{rem // 60:02d}m, {summary['total_meters'] / 1000:.1f} km"
        )

    pd.DataFrame(records).to_csv(dst_path, index=False)

    summary_path = dst_path.rsplit(".csv", 1)[0] + "-summary.csv"
    pd.DataFrame(
        [
            {
                "truck": truck,
                "stops": summary["stops"],
                "dumps": summary["dumps"],
                "total_seconds": summary["total_seconds"],
                "total_meters": summary["total_meters"],
            }
            for truck, summary in enumerate(summaries)
            if summary["stops"] > 0
        ]
    ).to_csv(summary_path, index=False)

    hours, rem = divmod(total_seconds, 3600)
    print(
        f"\nTotal: {hours}h{rem // 60:02d}m, {total_meters / 1000:.1f} km, "
        f"{total_dumps} viajes al relleno"
    )
    print(f"Solucion guardada en: {dst_path}")

    return {
        "total_seconds": total_seconds,
        "total_meters": total_meters,
        "total_dumps": total_dumps,
        "summaries": summaries,
    }
