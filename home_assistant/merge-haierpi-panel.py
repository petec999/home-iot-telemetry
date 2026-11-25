#!/usr/bin/env python3
"""Merge HaierPi 1.4.5_1 diagnostics into EXISTING 'Pompa ciepła' dashboard tab.

Clean redundant read-only cards, remove the unavailable COP tile/graphs,
append all 14 diagnostics from our GitHub release, move the home Zigbee sensor
card into Klimatyzacja, and retire the four temporary HaierPi-only tabs.

Uses the *official HA Lovelace WebSocket API*, full backup before save;
no changes to .storage files, configuration.yaml, automations, or NanoPi.
Run in Home Assistant Terminal/SSH add-on with Supervisor API permission.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import urllib.request

# Reuse the tested minimal HA WebSocket client from a PINNED commit in this repo.
# This makes the command standalone with Python stdlib, without pip or HA restart.
HELPERS_URL = (
    "https://raw.githubusercontent.com/petec999/home-iot-telemetry/"
    "626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/"
    "home_assistant/add-haierpi-views.py"
)
EXTRA_PATHS = {"haierpi-przeglad","haierpi-cykle","haierpi-obieg","haierpi-bilans"}
COP_MISSING = "sensor.haier_cop_chwilowy"
ROOM = "sensor.temperature_and_humidity_sensor_5_temperatura"
ROOM_ENTITIES = [
    {"entity": ROOM, "name": "Temperatura w domu (Zigbee)"},
    {"entity": "sensor.temperature_and_humidity_sensor_5_wilgotnosc",
     "name": "Wilgotność w domu (Zigbee)"},
    {"entity": "sensor.temperature_and_humidity_sensor_5_natezenie_oswietlenia",
     "name": "Natężenie światła w domu (Zigbee)"},
]
NEW_TITLES = {
    "Cykle i defrost · HaierPi 1.4.5_1",
    "Dane cykli i defrostów (RAM)",
    "Odszranianie · warunki i ryzyko",
    "Diagnostyka obiegu · 6 nowych wskaźników",
    "Sprężarka · fakt/zadane (24 h)",
    "Starty sprężarki i defrostu (48 h)",
    "Różnice temperatur obiegu (24 h)",
    "Różnica ciśnień czynnika (24 h)",
}

def helper_api():
    with urllib.request.urlopen(HELPERS_URL,timeout=25) as response:
        source=response.read(40_000).decode("utf-8")
    # The helper source is anchored to a reviewed commit.
    scope={"__name__":"haierpi_helper_pinned"}
    exec(compile(source,HELPERS_URL,"exec"),scope)
    return scope

def entity_in(row):
    return row if isinstance(row,str) else row.get("entity") if isinstance(row,dict) else None

def remove_broken_cop(card):
    """Drop only broken COP entity cards/graphs. Never delete a real COP sensor."""
    if not isinstance(card,dict):
        return card
    card=copy.deepcopy(card)
    if card.get("type") in ("gauge","entity","tile") and card.get("entity")==COP_MISSING:
        return None
    if card.get("type") in ("history-graph","statistics-graph","entities"):
        if isinstance(card.get("entities"),list):
            card["entities"]=[row for row in card["entities"] if entity_in(row)!=COP_MISSING]
            if not card["entities"]:
                return None
    if card.get("type")=="markdown" and (
            str(card.get("content","")).lstrip().startswith("*COP jest szacowany z przepływu")):
        # Old explanatory caption for the broken instantaneous COP sensor.
        return None
    if isinstance(card.get("cards"),list):
        card["cards"]=[c for item in card["cards"] if (c:=remove_broken_cop(item)) is not None]
        if not card["cards"]:
            return None
    return card

def identifiers(card):
    if not isinstance(card,dict):
        return set()
    result=set()
    if isinstance(card.get("entity"),str): result.add(card["entity"])
    for row in card.get("entities",[]):
        item=entity_in(row)
        if item: result.add(item)
    for sub in card.get("cards",[]):
        result.update(identifiers(sub))
    return result

def new_diagnostics(views):
    by_path={v["path"]:v for v in views}
    if set(by_path)!=EXTRA_PATHS:
        raise RuntimeError("Unexpected versioned dashboard JSON")
    cycles=by_path["haierpi-cykle"]["cards"]
    circuit=by_path["haierpi-obieg"]["cards"]
    def one(cards, kind, title):
        matched=[card for card in cards
                 if card.get("type")==kind and card.get("title")==title]
        if len(matched)!=1:
            raise RuntimeError("Unexpected diagnostics layout: "+title)
        return copy.deepcopy(matched[0])
    selection=[
        one(cycles,"markdown","Podsumowanie pracy sprężarki i odszraniania"),
        one(cycles,"entities","Wszystkie liczniki z HaierPi (RAM)"),
        one(cycles,"entities","Odszranianie · kontekst"),
        one(circuit,"entities","Sześć obliczanych parametrów 1.4.5_1"),
        one(cycles,"history-graph","Częstotliwość sprężarki (24 h)"),
        one(cycles,"history-graph","Starty sprężarki i defrostów (48 h)"),
        one(circuit,"history-graph","Obliczone różnice temperatur · °C (24 h)"),
        one(circuit,"history-graph","Różnica ciśnień czynnika · MPa (24 h)"),
    ]
    renamed=[
        "Cykle i defrost · HaierPi 1.4.5_1",
        "Dane cykli i defrostów (RAM)",
        "Odszranianie · warunki i ryzyko",
        "Diagnostyka obiegu · 6 nowych wskaźników",
        "Sprężarka · fakt/zadane (24 h)",
        "Starty sprężarki i defrostu (48 h)",
        "Różnice temperatur obiegu (24 h)",
        "Różnica ciśnień czynnika (24 h)",
    ]
    for card,name in zip(selection,renamed):
        card["title"]=name
    required={
        "sensor.haierpi_diagnostics_compressor_starts_today",
        "sensor.haierpi_diagnostics_completed_compressor_cycles_today",
        "sensor.haierpi_diagnostics_compressor_run_today",
        "sensor.haierpi_diagnostics_last_compressor_cycle",
        "sensor.haierpi_diagnostics_defrost_starts_today",
        "sensor.haierpi_diagnostics_defrost_run_today",
        "sensor.haierpi_diagnostics_completed_defrost_cycles_today",
        "sensor.haierpi_diagnostics_last_defrost_cycle",
        "sensor.haierpi_advanced_diagnostics_co_water_delta_t",
        "sensor.haierpi_advanced_diagnostics_refrigerant_saturation_lift",
        "sensor.haierpi_advanced_diagnostics_ambient_evaporation_approach",
        "sensor.haierpi_advanced_diagnostics_discharge_condensing_gap",
        "sensor.haierpi_advanced_diagnostics_refrigerant_pressure_delta",
        "sensor.haierpi_advanced_diagnostics_compressor_frequency_deviation",
    }
    missing=[k for k in required if not any(k in json.dumps(c) for c in selection)]
    if missing: raise RuntimeError("Missing diagnostic entities: "+str(missing))
    return selection

def dedupe_entity_rows(card,seen):
    """Drop repeated static entity rows; preserve graphs and controls."""
    if not isinstance(card,dict): return card
    card=copy.deepcopy(card)
    if card.get("type")=="entities" and isinstance(card.get("entities"),list):
        rows=[]
        for row in card["entities"]:
            ent=entity_in(row)
            if ent and ent in seen:
                continue
            if ent: seen.add(ent)
            rows.append(row)
        # A section header without any following entity rows is redundant.
        out=[]
        for i,row in enumerate(rows):
            if isinstance(row,dict) and row.get("type")=="section":
                if not any(entity_in(other) for other in rows[i+1:]
                           if not (isinstance(other,dict) and other.get("type")=="section")):
                    continue
            out.append(row)
        card["entities"]=out
        if not any(entity_in(row) for row in out):
            return None
    if isinstance(card.get("cards"),list):
        card["cards"]=[c for sub in card["cards"]
                         if (c:=dedupe_entity_rows(sub,seen)) is not None]
        if not card["cards"]: return None
    return card

def transform(config, release_views):
    output=copy.deepcopy(config)
    if not isinstance(output,dict) or not isinstance(output.get("views"),list):
        raise RuntimeError("Current dashboard is not UI-editable")
    if output.get("strategy"):
        raise RuntimeError("Current dashboard is generated using strategy")
    pump=[v for v in output["views"] if v.get("path")=="pompa-ciepla"]
    ac=[v for v in output["views"] if v.get("path")=="klimatyzacja"]
    if len(pump)!=1 or len(ac)!=1:
        raise RuntimeError("Expected original Pompa ciepła and Klimatyzacja views")
    pump=pump[0]
    ac=ac[0]
    if not isinstance(pump.get("cards"),list):
        raise RuntimeError("Pompa ciepła lacks the expected Lovelace cards")
    if not isinstance(ac.get("sections"),list) or not ac["sections"]:
        raise RuntimeError("Klimatyzacja lacks expected sections")

    new_cards=new_diagnostics(release_views)
    original=[]
    for item in pump["cards"]:
        if item.get("title") in NEW_TITLES:
            continue # idempotent rerun
        if str(item.get("title","")).strip().casefold()=="temperatura dom":
            # All three original sensors are displayed in Klimatyzacja instead.
            continue
        filtered=remove_broken_cop(item)
        if filtered is not None: original.append(filtered)

    # Integrate diagnostics directly after the original circuit gauges/charts.
    insert=next((i+1 for i,c in enumerate(original)
                 if c.get("type")=="vertical-stack" and any(
                    "sensor.haierpi_superheat" in identifiers(sub)
                    for sub in c.get("cards",[]))),len(original))
    original[insert:insert]=new_cards
    seen=set()
    pump["cards"]=[c for item in original if (c:=dedupe_entity_rows(item,seen)) is not None]

    climate_cards=ac["sections"][0].get("cards")
    if not isinstance(climate_cards,list):
        raise RuntimeError("Klimatyzacja section layout unknown")
    climate_cards[:]=[card for card in climate_cards
                      if card.get("title")!="Warunki w domu · Zigbee"]
    conditions={
        "type":"entities",
        "title":"Warunki w domu · Zigbee",
        "show_header_toggle":False,
        "entities":copy.deepcopy(ROOM_ENTITIES),
    }
    insert=next((i+1 for i,c in enumerate(climate_cards)
                 if c.get("type")=="thermostat"),1)
    climate_cards.insert(insert,conditions)
    graph=next((c for c in climate_cards
                if c.get("type")=="history-graph"
                and str(c.get("title","")).startswith("Klimatyzacja – temperatura pomieszczenia")),None)
    if graph is not None:
        graph.setdefault("entities",[])
        if ROOM not in [entity_in(row) for row in graph["entities"]]:
            graph["entities"].append({"entity":ROOM,"name":"Temperatura w domu (Zigbee)"})

    # Remove ONLY four temporary diagnostics tabs, never unrelated user views.
    output["views"]=[v for v in output["views"] if v.get("path") not in EXTRA_PATHS]
    if any(COP_MISSING in json.dumps(c) for c in pump["cards"]):
        raise RuntimeError("Broken instantaneous COP card reference still present")
    if len([v for v in output["views"] if v.get("path")=="pompa-ciepla"])!=1:
        raise RuntimeError("Pump tab missing after merge")
    for c in new_cards:
        if c["title"] not in [item.get("title") for item in pump["cards"]]:
            raise RuntimeError("Diagnostic card was dropped by dedup: "+c["title"])
    return output

def main():
    helpers=helper_api()
    views=helpers["get_release_views"]()
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise RuntimeError("Run in Home Assistant Terminal & SSH (not root@HaierPi).")
    if os.environ.get("SUPERVISOR_TOKEN"):
        host,port,path="supervisor",80,"/core/websocket"
    else:
        host=os.environ.get("HA_WS_HOST","homeassistant")
        port=int(os.environ.get("HA_WS_PORT","8123"))
        path="/api/websocket"
    ws=helpers["WS"](host,port,path)
    try:
        if ws.recv().get("type")!="auth_required":
            raise RuntimeError("Unexpected HA authentication handshake")
        ws.send({"type":"auth","access_token":token})
        if ws.recv().get("type")!="auth_ok":
            raise RuntimeError("Home Assistant token rejected")
        original=ws.call("lovelace/config",force=True)
        result=transform(original,views)
        if original==result:
            print("Already merged and up to date. Nothing changed.")
            return
        if ws.call("lovelace/config",force=True)!=original:
            raise RuntimeError("Dashboard changed concurrently, retry")
        backup=helpers["save_backup"](original)
        print("Full dashboard backup:",backup)
        ws.call("lovelace/config/save",config=result)
        if ws.call("lovelace/config",force=True)!=result:
            raise RuntimeError("Save verification failed; backup is "+str(backup))
        print("SUCCESS: Pompa ciepła now contains all 14 diagnostic sensors.")
        print("SUCCESS: removed the old unavailable COP card and redundant data rows.")
        print("SUCCESS: Klimatyzacja includes home Zigbee temperature, humidity and its graph.")
        print("SUCCESS: retired 4 temporary diagnostic-only tabs.")
        print("Other views, controls, automations and NanoPi are unchanged. Refresh HA.")
    finally:
        ws.close()

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR: "+str(exc),file=sys.stderr)
        sys.exit(1)
