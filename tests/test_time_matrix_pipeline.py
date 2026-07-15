import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code" / "pipeline"))

import time_matrix as tm


def test_load_points_drops_duplicate_ids(tmp_path, monkeypatch, capsys):
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
        "TEST1,,CHIHUAHUA,28.59364,-105.888562\n"
        "TEST1,,CHIHUAHUA,28.59364,-105.888562\n"
    )

    monkeypatch.setattr(tm, "LANDFILL_AND_DEPOT_SRC", str(depot_landfill_csv))
    monkeypatch.setattr(tm, "OXXO_STOPS_SRC", str(stops_csv))

    points = tm.TimeMatrixBuilder().load_points()

    assert points["id"].is_unique
    assert list(points["id"]).count("STOP::TEST1") == 1
    assert "Descartados 1 puntos duplicados" in capsys.readouterr().out


def test_load_points_keeps_distinct_ids(tmp_path, monkeypatch):
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

    monkeypatch.setattr(tm, "LANDFILL_AND_DEPOT_SRC", str(depot_landfill_csv))
    monkeypatch.setattr(tm, "OXXO_STOPS_SRC", str(stops_csv))

    points = tm.TimeMatrixBuilder().load_points()

    assert len(points) == 4
    assert points["id"].is_unique
