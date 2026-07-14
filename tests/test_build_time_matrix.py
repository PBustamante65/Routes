import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import build_time_matrix as btm


def test_load_points_orders_depot_and_landfill_first(tmp_path, monkeypatch):
    depot_landfill_csv = tmp_path / "landfill-and-depot.csv"
    depot_landfill_csv.write_text(
        "tienda,direccion,ciudad,latitud,longitud\n"
        "RELLENO SANITARIO,addr1,CHIHUAHUA,28.7,-106.0\n"
        "DIPACSA,addr2,CHIHUAHUA,28.69,-106.12\n"
    )
    stops_csv = tmp_path / "oxxo-stops.csv"
    stops_csv.write_text(
        "tienda,direccion,ciudad,latitud,longitud\n"
        "ALDAMA,addr3,CHIHUAHUA,28.63,-106.07\n"
        "AMAZONAS,addr4,CHIHUAHUA,28.77,-106.16\n"
    )

    monkeypatch.setattr(btm, "LANDFILL_AND_DEPOT_SRC", str(depot_landfill_csv))
    monkeypatch.setattr(btm, "OXXO_STOPS_SRC", str(stops_csv))

    points = btm.load_points()

    assert list(points["tipo"]) == ["DEPOT", "LANDFILL", "STOP", "STOP"]
    assert points.loc[0, "id"] == "DEPOT::DIPACSA"
    assert points.loc[1, "id"] == "LANDFILL::RELLENO_SANITARIO"
    assert set(points.loc[2:, "id"]) == {"STOP::ALDAMA", "STOP::AMAZONAS"}


def test_load_points_drops_missing_coordinates(tmp_path, monkeypatch):
    depot_landfill_csv = tmp_path / "landfill-and-depot.csv"
    depot_landfill_csv.write_text(
        "tienda,direccion,ciudad,latitud,longitud\n"
        "RELLENO SANITARIO,addr1,CHIHUAHUA,28.7,-106.0\n"
        "DIPACSA,addr2,CHIHUAHUA,28.69,-106.12\n"
    )
    stops_csv = tmp_path / "oxxo-stops.csv"
    stops_csv.write_text(
        "tienda,direccion,ciudad,latitud,longitud\n"
        "ALDAMA,addr3,CHIHUAHUA,28.63,-106.07\n"
        "MISSING,addr4,CHIHUAHUA,,\n"
    )

    monkeypatch.setattr(btm, "LANDFILL_AND_DEPOT_SRC", str(depot_landfill_csv))
    monkeypatch.setattr(btm, "OXXO_STOPS_SRC", str(stops_csv))

    points = btm.load_points()

    assert len(points) == 3
    assert "STOP::MISSING" not in set(points["id"])


def test_chunk_indices_covers_range_without_gaps():
    chunks = list(btm.chunk_indices(5, 2))
    assert chunks == [(0, 2), (2, 4), (4, 5)]


def test_chunk_indices_single_batch_when_batch_size_exceeds_n():
    assert list(btm.chunk_indices(3, 10)) == [(0, 3)]


def test_batch_size_stays_under_osrm_table_size_cap():
    """The public OSRM demo server rejects requests where
    sources x destinations exceeds 10,000 ("Too many table coordinates")."""
    points = btm.load_points()
    assert btm.BATCH_SIZE * len(points) <= 10000


def test_build_duration_matrix_places_batches_in_correct_cells(monkeypatch):
    import pandas as pd

    points = pd.DataFrame(
        {
            "id": ["DEPOT::A", "LANDFILL::B", "STOP::C"],
            "tienda": ["A", "B", "C"],
            "tipo": ["DEPOT", "LANDFILL", "STOP"],
            "latitud": [28.0, 28.1, 28.2],
            "longitud": [-106.0, -106.1, -106.2],
        }
    )

    fake_responses = {
        (0, 2): [[0, 10, 20], [10, 0, 30]],
        (2, 3): [[20, 30, 0]],
    }

    def fake_fetch(coords_param, source_indices, all_indices):
        key = (source_indices.start, source_indices.stop)
        return fake_responses[key]

    monkeypatch.setattr(btm, "BATCH_SIZE", 2)
    monkeypatch.setattr(btm, "REQUEST_DELAY_SECONDS", 0)
    with patch.object(btm, "fetch_duration_batch", side_effect=fake_fetch):
        matrix = btm.build_duration_matrix(points)

    expected = np.array([[0, 10, 20], [10, 0, 30], [20, 30, 0]])
    assert np.array_equal(matrix, expected)
