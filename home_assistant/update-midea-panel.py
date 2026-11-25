#!/usr/bin/env python3
"""Update only the existing Klimatyzacja view using actual HA registry IDs."""
from __future__ import annotations

import copy
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HELPER = ("https://raw.githubusercontent.com/petec999/home-iot-telemetry/"
          "626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py")
ROOM = "sensor.temperature_and_humidity_sensor_5_temperatura"
ROOM_ROWS = {
    ROOM: ("Temperatura w domu", "mdi:home-thermometer"),
    "sensor.temperature_and_humidity_sensor_5_wilgotnosc": ("Wilgotność w domu", "mdi:water-percent"),
    "sensor.temperature_and_humidity_sensor_5_natezenie_oswietlenia": ("Natężenie światła w domu", "mdi:brightness-5"),
}
FIELDS = {
    "eco": ("switch", "ECO", "mdi:leaf"),
    "turbo": ("switch", "Turbo", "mdi:fan-plus"),
    "sleep": ("switch", "Tryb nocny", "mdi:weather-night"),
    "display_on": ("switch", "Wyświetlacz", "mdi:led-on"),
    "indoor_temperature": ("sensor", "Temperatura klimatyzatora", "mdi:thermometer"),
    "outdoor_temperature": ("sensor", "Temperatura zewnętrzna", "mdi:thermometer"),
    "error_code": ("sensor", "Kod błędu", "mdi:alert-circle-outline"),
    "filter_alert": ("binary_sensor", "Alarm filtra", "mdi:air-filter"),
}
TITLES = {"Midea · sterowanie", "Midea · temperatury", "Midea · diagnostyka",
          "Midea · historia temperatur (24 h)", "Warunki w domu"}


def row_entity(row):
    return row if isinstance(row, str) else row.get("entity") if isinstance(row, dict) else None


def refs(obj):
    if isinstance(obj, dict):
        result = {obj["entity"]} if isinstance(obj.get("entity"), str) else set()
        for key in ("entities", "cards", "sections"):
            for item in obj.get(key, []):
                if key == "entities":
                    if entity := row_entity(item):
                        result.add(entity)
                else:
                    result.update(refs(item))
        return result
    return set()


def resolve(view, registry, states):
    """Select the single Midea climate already present in this view; never another device."""
    live = {s["entity_id"] for s in states}
    present = refs(view)
    entries = [r for r in registry if r.get("platform") == "midea_cloud_control"]
    climate = [r for r in entries if r["entity_id"].startswith("climate.")
               and r["entity_id"] in present and r["entity_id"] in live
               and not r.get("disabled_by")]
    if len(climate) != 1:
        raise RuntimeError("Expected exactly one existing Midea climate entity in Klimatyzacja; no changes saved")
    target = climate[0]
    fields = {}
    for field, (domain, _, _) in FIELDS.items():
        matches = [r for r in entries if r.get("unique_id") == str(target["unique_id"]) + "_" + field
                   and r["entity_id"].startswith(domain + ".")
                   and r.get("device_id") == target.get("device_id")]
        if len(matches) > 1:
            raise RuntimeError("Ambiguous registry field: " + field)
        if matches and not matches[0].get("disabled_by") and matches[0]["entity_id"] in live:
            fields[field] = matches[0]["entity_id"]
    rooms = {e for e in ROOM_ROWS if e in live}
    return target["entity_id"], fields, rooms


def row(entity, name, icon=None):
    result = {"entity": entity, "name": name}
    if icon:
        result["icon"] = icon
    return result


def clean(card, managed, climate):
    """Remove only duplicate managed standard cards/rows; retain unrelated custom content."""
    card = copy.deepcopy(card)
    kind = card.get("type")
    used = refs(card)
    # Our own titled cards are replaceable only when they contain no foreign entities.
    if card.get("title") in TITLES and used and used <= managed:
        return None
    if kind in ("tile", "entity", "sensor", "gauge") and card.get("entity") in managed:
        return None
    if kind == "entities" and isinstance(card.get("entities"), list):
        old = card["entities"]
        card["entities"] = [r for r in old if row_entity(r) not in managed]
        if old and not card["entities"]:
            return None
    if kind == "history-graph" and used and used <= (managed | {climate}) and (
        str(card.get("title", "")).startswith("Klimatyzacja – temperatura pomieszczenia")
        or used == {ROOM}
    ):
        return None
    if kind in ("grid", "vertical-stack", "horizontal-stack") and isinstance(card.get("cards"), list):
        old = card["cards"]
        card["cards"] = [c for item in old if (c := clean(item, managed, climate)) is not None]
        if old and not card["cards"]:
            return None
    return card


def transform(config, registry, states):
    result = copy.deepcopy(config)
    if not isinstance(result, dict) or result.get("strategy") or not isinstance(result.get("views"), list):
        raise RuntimeError("Dashboard is not editable storage configuration")
    views = [v for v in result["views"] if v.get("path") == "klimatyzacja"]
    if len(views) != 1:
        raise RuntimeError("Expected one Klimatyzacja view")
    view = views[0]
    climate, fields, rooms = resolve(view, registry, states)
    if not {"indoor_temperature", "outdoor_temperature"} <= fields.keys():
        raise RuntimeError("Missing Midea 0.2.0 temperature entities; dashboard unchanged")
    managed = set(fields.values()) | rooms
    # Preserve the existing thermostat and every unrelated card.
    if isinstance(view.get("sections"), list) and view["sections"]:
        containers = view["sections"]
    elif isinstance(view.get("cards"), list):
        containers = [view]
    else:
        raise RuntimeError("Unknown Klimatyzacja layout")
    for container in containers:
        if not isinstance(container.get("cards"), list):
            raise RuntimeError("Unknown card layout")
        container["cards"] = [c for item in container["cards"]
                              if (c := clean(item, managed, climate)) is not None]
    target = next((c for c in containers if climate in refs(c)), containers[0])
    cards = target["cards"]

    def field_row(field):
        return row(fields[field], FIELDS[field][1], FIELDS[field][2])

    def entities(title, rows):
        return {"type": "entities", "title": title, "show_header_toggle": False, "entities": rows}

    new = []
    if switches := [field_row(f) for f in ("eco", "turbo", "sleep", "display_on") if f in fields]:
        new.append(entities("Midea · sterowanie", switches))
    new.append(entities("Midea · temperatury", [field_row(f) for f in
                                                ("indoor_temperature", "outdoor_temperature")]))
    if room_rows := [row(e, *label) for e, label in ROOM_ROWS.items() if e in rooms]:
        new.append(entities("Warunki w domu", room_rows))
    graph_rows = [row(fields[f], FIELDS[f][1]) for f in ("indoor_temperature", "outdoor_temperature")]
    if ROOM in rooms:
        graph_rows.append(row(ROOM, "Temperatura w domu"))
    new.append({"type": "history-graph", "title": "Midea · historia temperatur (24 h)",
                "hours_to_show": 24, "entities": graph_rows})
    if diagnostics := [field_row(f) for f in ("error_code", "filter_alert") if f in fields]:
        new.append(entities("Midea · diagnostyka", diagnostics))
    insert = next((i + 1 for i, c in enumerate(cards) if climate in refs(c)), len(cards))
    cards[insert:insert] = new
    return result


def save_backup(config):
    root = Path(os.environ.get("HA_CONFIG_DIR", "/config"))
    if not (root / "configuration.yaml").exists():
        raise RuntimeError("Home Assistant configuration directory not found")
    folder = root / "lovelace-backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = folder / ("before-midea-" + stamp + ".json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
    return path


def main():
    token = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise RuntimeError("HA Terminal needs Supervisor API permission or HA_TOKEN")
    with urllib.request.urlopen(HELPER, timeout=25) as response:
        source = response.read(40000)
    scope = {"__name__": "pinned_ws_helper"}
    exec(compile(source, HELPER, "exec"), scope)
    if os.environ.get("SUPERVISOR_TOKEN"):
        host, port, path = "supervisor", 80, "/core/websocket"
    else:
        host, port, path = os.environ.get("HA_WS_HOST", "homeassistant"), int(os.environ.get("HA_WS_PORT", "8123")), "/api/websocket"
    ws = scope["WS"](host, port, path)
    try:
        if ws.recv().get("type") != "auth_required":
            raise RuntimeError("Unexpected authentication handshake")
        ws.send({"type": "auth", "access_token": token})
        if ws.recv().get("type") != "auth_ok":
            raise RuntimeError("HA authentication refused")
        original = ws.call("lovelace/config", force=True)
        registry = ws.call("config/entity_registry/list")
        states = ws.call("get_states")
        result = transform(original, registry, states)
        if result == original:
            print("Already up to date; no changes.")
            return
        if "--dry-run" in sys.argv:
            print("Dry run: only Klimatyzacja would be changed.")
            return
        if ws.call("lovelace/config", force=True) != original:
            raise RuntimeError("Dashboard changed concurrently; retry")
        backup = save_backup(original)
        print("Backup:", backup)
        ws.call("lovelace/config/save", config=result)
        if ws.call("lovelace/config", force=True) != result:
            raise RuntimeError("Save verification failed; backup: " + str(backup))
        print("SUCCESS: Klimatyzacja updated; other views and device settings unchanged.")
    finally:
        ws.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
