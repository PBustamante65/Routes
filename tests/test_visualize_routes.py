import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import visualize_routes as vr


@pytest.fixture
def points():
    return pd.DataFrame(
        {
            "id": ["DEPOT::D", "LANDFILL::L", "STOP::A", "STOP::B"],
            "tienda": ["D", "L", "A", "B"],
            "tipo": ["DEPOT", "LANDFILL", "STOP", "STOP"],
            "latitud": [28.69, 28.70, 28.63, 28.64],
            "longitud": [-106.12, -106.03, -106.07, -106.08],
        }
    )


@pytest.fixture
def solution():
    return pd.DataFrame(
        {
            "truck": [0, 0, 0, 1, 1],
            "seq": [0, 1, 2, 0, 1],
            "id": ["STOP::A", "STOP::B", "LANDFILL::L", "STOP::B", "LANDFILL::L"],
            "tienda": ["A", "B", "L", "B", "L"],
            "tipo": ["STOP", "STOP", "LANDFILL", "STOP", "LANDFILL"],
            "arrival_seconds": [300, 700, 2000, 400, 1500],
            "load_after_cbm": [0.9, 1.8, 0.0, 0.9, 0.0],
        }
    )


def test_build_truck_path_closes_loop_at_depot(points, solution):
    path = vr.build_truck_path(solution[solution["truck"] == 0], points, 0)

    assert path[0][:2] == (28.69, -106.12)
    assert path[-1][:2] == (28.69, -106.12)
    assert [label for _, _, label in path] == [
        "DEPOT", "STOP::A", "STOP::B", "LANDFILL::L", "DEPOT",
    ]


def test_truck_color_cycles():
    assert vr.truck_color(0) == vr.truck_color(len(vr.TRUCK_COLORS))
    assert vr.truck_color(1) != vr.truck_color(2)


def test_format_minutes():
    assert vr.format_minutes(0) == "0h00m"
    assert vr.format_minutes(3900) == "1h05m"


def test_build_map_has_layer_per_active_truck(points, solution):
    html = vr.build_map(solution, points).get_root().render()

    assert "Camion 0 (2 paradas)" in html
    assert "Camion 1 (1 paradas)" in html
    assert "DEPOT: D" in html
    assert "LANDFILL: L" in html


def test_build_map_written_to_file(tmp_path, points, solution):
    out = tmp_path / "mapa.html"
    vr.build_map(solution, points).save(str(out))
    assert out.exists() and out.stat().st_size > 0
