import time
import numpy as np
import pandas as pd
import requests

LANDFILL_AND_DEPOT_SRC = "Data/landfill-and-depot.csv"
OXXO_STOPS_SRC = "Data/pipeline/oxxo-stops.csv"
TIME_MATRIX_DST = "Data/pipeline/time-matrix-seconds.csv"
DISTANCE_MATRIX_DST = "Data/pipeline/distance-matrix-meters.csv"
POINTS_INDEX_DST = "Data/pipeline/points-index.csv"

OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/{coords}"
BATCH_SIZE = (
    40  # OSRM's public demo server caps sources x destinations at 10,000 per request
)
REQUEST_DELAY_SECONDS = 1
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5


class TimeMatrixBuilder:

    def __init__(self):
        pass

    def _slug(self, name):
        return str(name).strip().replace(" ", "_")

    def load_points(self):

        depot_landfill = pd.read_csv(LANDFILL_AND_DEPOT_SRC).dropna(subset=["tienda"])
        stops = pd.read_csv(OXXO_STOPS_SRC).dropna(subset=["tienda"])

        is_landfill = depot_landfill["tienda"].str.upper() == "RELLENO SANITARIO"
        landfill = depot_landfill[is_landfill].copy()
        depot = depot_landfill[~is_landfill].copy()

        depot["tipo"] = "DEPOT"
        landfill["tipo"] = "LANDFILL"
        stops["tipo"] = "STOP"

        points = pd.concat([depot, landfill, stops], ignore_index=True)

        with_coords = points.dropna(subset=["latitud", "longitud"]).reset_index(
            drop=True
        )
        dropped = len(points) - len(with_coords)
        if dropped:
            print(f"Descartados {dropped} puntos sin coordenadas.")
        points = with_coords

        points["id"] = points["tipo"] + "::" + points["tienda"].apply(self._slug)

        deduped = points.drop_duplicates(subset="id", keep="first").reset_index(drop=True)
        duplicates = len(points) - len(deduped)
        if duplicates:
            print(f"Descartados {duplicates} puntos duplicados (mismo id).")
        points = deduped

        return points[["id", "tienda", "tipo", "latitud", "longitud"]]

    def chunk_indices(self, n, batch_size):

        for start in range(0, n, batch_size):
            yield start, min(start + batch_size, n)

    def fetch_matrix_batch(self, coords_param, source_indices, all_indices):

        sources = ";".join(str(i) for i in source_indices)
        destinations = ";".join(str(i) for i in all_indices)
        url = OSRM_TABLE_URL.format(coords=coords_param)
        params = {
            "sources": sources,
            "destinations": destinations,
            "annotations": "duration,distance",
        }

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                body = response.json()
                return body["durations"], body["distances"]
            except (requests.RequestException, KeyError, ValueError) as exc:
                last_error = exc
                print(f"Intento {attempt}/{MAX_RETRIES} fallido: {exc}")
                time.sleep(RETRY_WAIT_SECONDS)
        raise RuntimeError(
            f"No se pudo obtener el batch tras {MAX_RETRIES} intentos: {last_error}"
        )

    def build_matrices(self, points):

        n = len(points)
        coords_param = ";".join(
            f"{lon},{lat}" for lat, lon in zip(points["latitud"], points["longitud"])
        )
        all_indices = range(n)

        durations_matrix = np.full((n, n), np.nan)
        distances_matrix = np.full((n, n), np.nan)

        for start, end in self.chunk_indices(n, BATCH_SIZE):
            source_indices = range(start, end)
            durations, distances = self.fetch_matrix_batch(
                coords_param, source_indices, all_indices
            )
            durations_matrix[start:end, :] = durations
            distances_matrix[start:end, :] = distances
            print(f"Batch {start}-{end} de {n} listo.")
            time.sleep(REQUEST_DELAY_SECONDS)

        return durations_matrix, distances_matrix

    def main(self):

        points = self.load_points()
        print(f"Calculando matrices de tiempo y distancia para {len(points)} puntos...")

        durations_matrix, distances_matrix = self.build_matrices(points)

        ids = points["id"]
        pd.DataFrame(durations_matrix, index=ids, columns=ids).to_csv(TIME_MATRIX_DST)
        print(f"Matriz de tiempos guardada en: {TIME_MATRIX_DST}")

        pd.DataFrame(distances_matrix, index=ids, columns=ids).to_csv(
            DISTANCE_MATRIX_DST
        )
        print(f"Matriz de distancias guardada en: {DISTANCE_MATRIX_DST}")

        points.to_csv(POINTS_INDEX_DST, index=False)
        print(f"Indice de puntos guardado en: {POINTS_INDEX_DST}")
