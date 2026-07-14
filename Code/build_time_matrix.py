"""
Builds a full pairwise travel-time matrix (depot + landfill + Oxxo stops)
using OSM's OSRM public routing API (/table service).

Usage:
    python3 build_time_matrix.py
"""

import time

import numpy as np
import pandas as pd
import requests

LANDFILL_AND_DEPOT_SRC = "Data/landfill-and-depot.csv"
OXXO_STOPS_SRC = "Data/oxxo-stops.csv"
MATRIX_DST = "Data/time-matrix-seconds.csv"
POINTS_INDEX_DST = "Data/points-index.csv"

OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/{coords}"
BATCH_SIZE = 40  # OSRM's public demo server caps sources x destinations at 10,000 per request
REQUEST_DELAY_SECONDS = 1
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5


def _slug(name):
    return str(name).strip().replace(" ", "_")


def load_points():
    """Loads and tags all points, with depot and landfill placed first.

    Ids are prefixed by role (DEPOT::/LANDFILL::/STOP::) so a store can
    never be mistaken for the depot or landfill, even if it shared a name.
    """
    depot_landfill = pd.read_csv(LANDFILL_AND_DEPOT_SRC).dropna(subset=["tienda"])
    stops = pd.read_csv(OXXO_STOPS_SRC).dropna(subset=["tienda"])

    is_landfill = depot_landfill["tienda"].str.upper() == "RELLENO SANITARIO"
    landfill = depot_landfill[is_landfill].copy()
    depot = depot_landfill[~is_landfill].copy()

    depot["tipo"] = "DEPOT"
    landfill["tipo"] = "LANDFILL"
    stops["tipo"] = "STOP"

    points = pd.concat([depot, landfill, stops], ignore_index=True)

    with_coords = points.dropna(subset=["latitud", "longitud"]).reset_index(drop=True)
    dropped = len(points) - len(with_coords)
    if dropped:
        print(f"Descartados {dropped} puntos sin coordenadas.")
    points = with_coords

    points["id"] = points["tipo"] + "::" + points["tienda"].apply(_slug)

    return points[["id", "tienda", "tipo", "latitud", "longitud"]]


def chunk_indices(n, batch_size):
    """Yields (start, end) index pairs covering range(n) in batch_size steps."""
    for start in range(0, n, batch_size):
        yield start, min(start + batch_size, n)


def fetch_duration_batch(coords_param, source_indices, all_indices):
    sources = ";".join(str(i) for i in source_indices)
    destinations = ";".join(str(i) for i in all_indices)
    url = OSRM_TABLE_URL.format(coords=coords_param)
    params = {
        "sources": sources,
        "destinations": destinations,
        "annotations": "duration",
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()["durations"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            last_error = exc
            print(f"Intento {attempt}/{MAX_RETRIES} fallido: {exc}")
            time.sleep(RETRY_WAIT_SECONDS)
    raise RuntimeError(f"No se pudo obtener el batch tras {MAX_RETRIES} intentos: {last_error}")


def build_duration_matrix(points):
    n = len(points)
    coords_param = ";".join(f"{lon},{lat}" for lat, lon in zip(points["latitud"], points["longitud"]))
    all_indices = range(n)

    matrix = np.full((n, n), np.nan)

    for start, end in chunk_indices(n, BATCH_SIZE):
        source_indices = range(start, end)
        durations = fetch_duration_batch(coords_param, source_indices, all_indices)
        matrix[start:end, :] = durations
        print(f"Batch {start}-{end} de {n} listo.")
        time.sleep(REQUEST_DELAY_SECONDS)

    return matrix


def main():
    points = load_points()
    print(f"Calculando matriz de tiempos para {len(points)} puntos...")

    matrix = build_duration_matrix(points)

    matrix_df = pd.DataFrame(matrix, index=points["id"], columns=points["id"])
    matrix_df.to_csv(MATRIX_DST)
    print(f"Matriz guardada en: {MATRIX_DST}")

    points.to_csv(POINTS_INDEX_DST, index=False)
    print(f"Indice de puntos guardado en: {POINTS_INDEX_DST}")


if __name__ == "__main__":
    main()
