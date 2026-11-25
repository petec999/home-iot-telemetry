#!/usr/bin/env python3
"""Check real HA dashboard entities vs pinned source of hpi v1.4.5_1."""
import ast
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
HPI = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "hpi"
DASHBOARDS = ROOT / "home_assistant" / "dashboards"

CYCLE = {
    "compressor_starts": "sensor.haierpi_diagnostics_compressor_starts_today",
    "compressor_seconds": "sensor.haierpi_diagnostics_compressor_run_today",
    "compressor_completed_cycles": "sensor.haierpi_diagnostics_completed_compressor_cycles_today",
    "compressor_last_cycle_seconds": "sensor.haierpi_diagnostics_last_compressor_cycle",
    "defrost_starts": "sensor.haierpi_diagnostics_defrost_starts_today",
    "defrost_seconds": "sensor.haierpi_diagnostics_defrost_run_today",
    "defrost_completed_cycles": "sensor.haierpi_diagnostics_completed_defrost_cycles_today",
    "defrost_last_cycle_seconds": "sensor.haierpi_diagnostics_last_defrost_cycle",
}
CIRCUIT = {
    "water_delta_t": "sensor.haierpi_advanced_diagnostics_co_water_delta_t",
    "saturation_lift": "sensor.haierpi_advanced_diagnostics_refrigerant_saturation_lift",
    "ambient_evaporating_approach": "sensor.haierpi_advanced_diagnostics_ambient_evaporation_approach",
    "discharge_condensing_gap": "sensor.haierpi_advanced_diagnostics_discharge_condensing_gap",
    "pressure_delta_mpa": "sensor.haierpi_advanced_diagnostics_refrigerant_pressure_delta",
    "compressor_frequency_error_hz": "sensor.haierpi_advanced_diagnostics_compressor_frequency_deviation",
}

def get_literal_assignment(file: Path, name: str):
    tree = ast.parse(file.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{file} has no literal {name}")

def check_card(card):
    assert isinstance(card, dict)
    ty = card.get("type")
    assert ty in {"markdown", "tile", "entities", "grid", "history-graph"}, f"Unknown card {ty}"
    if ty == "grid":
        assert card.get("cards")
        for child in card["cards"]:
            check_card(child)
    if ty == "tile":
        assert isinstance(card.get("entity"), str)
    if ty == "entities":
        assert all(isinstance(e, dict) and isinstance(e.get("entity"), str)
                   for e in card.get("entities", []))
    if ty == "history-graph":
        assert all(isinstance(e, dict) and isinstance(e.get("entity"), str)
                   for e in card.get("entities", []))
    if ty == "markdown":
        assert card.get("content")

def main():
    source_cycles = get_literal_assignment(
        HPI / "diagnostics" / "mqtt_cycle_bridge.py", "METRICS")
    source_circuit = get_literal_assignment(
        HPI / "diagnostics" / "mqtt_circuit_bridge.py", "METRIC_UNITS")
    assert set(source_cycles) == set(CYCLE), "Cycles changed in hpi release; update dashboard"
    assert set(source_circuit) == set(CIRCUIT), "Circuit metrics changed in hpi release"
    assert len(CYCLE) == 8 and len(CIRCUIT) == 6

    full_path = DASHBOARDS / "haierpi-centrum-1.4.5_1.yaml"
    single_path = DASHBOARDS / "haier-diagnostyka-view.yaml"
    full = yaml.safe_load(full_path.read_text(encoding="utf-8"))
    single = yaml.safe_load(single_path.read_text(encoding="utf-8"))
    assert isinstance(full, dict) and len(full.get("views", [])) == 4
    assert isinstance(single, dict) and "views" not in single
    paths = [view.get("path") for view in full["views"]]
    assert len(set(paths)) == 4

    for view in [*full["views"], single]:
        assert view.get("cards"), "View must contain cards"
        for card in view["cards"]:
            check_card(card)

    ids = set(CYCLE.values()) | set(CIRCUIT.values())
    for p in (full_path, single_path):
        source = p.read_text(encoding="utf-8")
        for entity in sorted(ids):
            assert entity in source, f"Missing {entity} in {p}"
        assert "entity: sensor.haier_cop_chwilowy" not in source
        assert "sensor.haier_bilans_cop_dobowy" in source
        assert "haierpi-pr8" not in source
        print(f"OK {p.name}: all {len(ids)} diagnostic entities; no unavailable COP card")

    print("OK: Verified against petec999/hpi v1.4.5_1 source, 4-view full dashboard and 1-view version")

if __name__ == "__main__":
    main()
