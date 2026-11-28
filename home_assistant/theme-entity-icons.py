#!/usr/bin/env python3
"""Theme existing Home Assistant dashboard icons, without changing entities or controls.
Dry run by default; --apply saves only Lovelace icons after a full local backup.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HELPER = ("https://raw.githubusercontent.com/petec999/home-iot-telemetry/"
          "626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py")
# Order matters: specific quantities before generic equipment words.
RULES = (
    (r"\b(cop|scop|sprawnosc|efficiency)\b", "chart-line"),
    (r"\b(defrost|odszranian\w*|szron\w*|tdef)\b", "snowflake-melt"),
    (r"\b(antifreeze|antyzamarz\w*|frost protection)\b", "snowflake-alert"),
    (r"\b(anti legionella|antylegionella|legionella|dezynfek\w*)\b", "shield-check"),
    (r"\b(error|fault|blad|bled\w*|awaria|alarm)\b", "alert-circle-outline"),
    (r"\b(rssi|signal|sygnal\w*|wifi|wi fi|linkquality)\b", "wifi"),
    (r"\b(firmware|version|wersja|update|aktualizacja)\b", "update"),
    (r"\b(energy|energia|kwh|zuzycie pradu|prad dzis|prad suma)\b", "lightning-bolt"),
    (r"\b(cieplo|heat energy|thermal energy)\b.*\b(dzis|suma|total|kwh)\b", "fire"),
    (r"\b(power|moc)\b.*\b(grzania|cieplna|odebrana|thermal|heat)\b", "fire"),
    (r"\b(power|moc|watt\w*)\b", "flash"),
    (r"\b(voltage|napiecie|volt\w*)\b", "sine-wave"),
    (r"\b(current|prad|amper\w*)\b", "current-ac"),
    (r"\b(starts?|starty|startow|zalaczen\w*|cycles?|cykle|cykli|licznik)\b(?!.*\b(runtime|run today|last|czas)\b)", "counter"),
    (r"\b(runtime|run today|last .*cycle|czas pracy|godziny pracy|uptime|duration)\b", "timer-outline"),
    (r"\b(fact|fset|frequency|czestotliw\w*|hz|flimit)\b", "sine-wave"),
    (r"\b(delta t|superheat|subcooling|przegrzanie|dochlodzenie|saturation lift|approach|condensing gap)\b", "thermometer-lines"),
    (r"\b(pressure|cisnien\w*|pdact|pdset|psact|psset)\b", "gauge"),
    (r"\b(eev|valve|zawor\w*)\b", "valve"),
    (r"\b(twi|two|water inlet|water outlet|temp\w* wody|temperatura zasilania|temperatura powrotu)\b", "water-thermometer"),
    (r"\b(tao|outdoor temperature|temperatura zewnetrzna)\b", "thermometer"),
    (r"\b(indoor temperature|temperatura w domu|temperatura domu|room temperature)\b", "home-thermometer"),
    (r"\b(temperature|temperatur\w*|tsat\w*|thi|tho|td|ts|tank temp)\b", "thermometer"),
    (r"\b(humidity|wilgotnosc|wilgotnosc\w*)\b", "water-percent"),
    (r"\b(illuminance|natezenie oswietlenia|lux)\b", "brightness-5"),
    (r"\b(flow|przeplyw\w*)\b", "waves-arrow-right"),
    (r"\b(fan|wentylator\w*|rpm)\b", "fan"),
    (r"\b(compressor|sprezark\w*)\b", "engine"),
    (r"\b(circulation|cyrkulac\w*|pump|pompa)\b", "water-pump"),
    (r"\b(heater|grzalka|grzalk\w*|radiator|grzejnik\w*)\b", "radiator"),
    (r"\b(dhw|cwu|zasobnik\w*|bojler\w*|boiler)\b", "water-boiler"),
    (r"\b(eco|oszczedn\w*)\b", "leaf"),
    (r"\b(turbo|boost)\b", "fan-plus"),
    (r"\b(quiet|silent|cichy|cisza|sleep|nocny)\b", "weather-night"),
    (r"\b(filter|filtr\w*)\b", "air-filter"),
    (r"\b(battery|bateria|akumulator\w*)\b", "battery"),
    (r"\b(gas|gaz|gazomierz)\b", "meter-gas"),
    (r"\b(water|woda|wodomierz|wody)\b", "water"),
    (r"\b(socket|outlet|gniazd\w*|plug)\b", "power-plug"),
    (r"\b(heating curve|krzywa grzewcza)\b", "chart-line"),
    (r"\b(adaptive|adaptacyjn\w*)\b", "tune"),
    (r"\b(display|wyswietlacz)\b", "monitor"),
    (r"\b(restart|reboot|reset)\b", "restart"),
    (r"\b(mqtt|rs485|modbus|register|rejestr\w*)\b", "lan"),
    (r"\b(disk|storage|dysk|pamiec)\b", "harddisk"),
    (r"\b(cpu|processor|procesor)\b", "cpu-64-bit"),
)
EXACT = {
    "sensor.haierpi_compressor_fact":"sine-wave",
    "sensor.haierpi_compressor_fset":"sine-wave",
    "sensor.haierpi_tao":"thermometer",
    "sensor.haierpi_tdef":"snowflake-melt",
    "sensor.haierpi_pump":"water-pump",
    "sensor.haierpi_3_way_valve":"valve",
    "sensor.haierpi_twi":"water-thermometer",
    "sensor.haierpi_two":"water-thermometer",
}
CLASSES = {
    "temperature":"thermometer","humidity":"water-percent","illuminance":"brightness-5",
    "pressure":"gauge","atmospheric_pressure":"gauge","power":"flash",
    "energy":"lightning-bolt","voltage":"sine-wave","current":"current-ac",
    "frequency":"sine-wave","power_factor":"chart-line","water":"water",
    "volume":"cup-water","volume_flow_rate":"waves-arrow-right","gas":"meter-gas",
    "duration":"timer-outline","distance":"map-marker-distance","speed":"speedometer",
    "data_rate":"swap-vertical","data_size":"database","signal_strength":"wifi",
    "carbon_dioxide":"molecule-co2","carbon_monoxide":"molecule-co",
    "pm25":"air-filter","pm10":"air-filter","volatile_organic_compounds":"air-filter",
    "sound_pressure":"volume-high","moisture":"water-alert",
}
DOMAINS = {"climate":"thermostat","water_heater":"water-boiler","fan":"fan",
           "vacuum":"robot-vacuum","media_player":"speaker","camera":"cctv",
           "automation":"robot","script":"script-text","scene":"palette",
           "input_datetime":"calendar-clock","timer":"timer-outline",
           "counter":"counter","weather":"weather-partly-cloudy","person":"account",
           "device_tracker":"map-marker","calendar":"calendar","number":"tune",
           "input_number":"tune","select":"form-select","input_select":"form-select"}
DYNAMIC_CLASSES = {"door","garage_door","window","opening","lock","motion","occupancy",
                   "presence","smoke","safety","problem","connectivity","battery",
                   "battery_charging","plug","running","power"}
CARD_TYPES = {"tile","entity","button"}
ROW_TYPES = {"entities","glance"}
CONTAINERS = {"grid","vertical-stack","horizontal-stack","conditional"}

def normalize(value):
    value = str(value).lower().replace("ł","l")
    value = "".join(c for c in unicodedata.normalize("NFKD",value) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+"," ",value).strip()

def icon_for(entity, attrs, registry):
    if not isinstance(entity,str) or "." not in entity:
        return None
    domain, key = entity.split(".",1)
    if registry.get("icon") or attrs.get("entity_picture"):
        return None
    dc = attrs.get("device_class") or registry.get("device_class") or registry.get("original_device_class")
    # Keep HA's dynamic safety/contact/battery icons and normal light/cover/lock icons.
    if domain in {"light","cover","lock","alarm_control_panel","sun"} or (domain=="binary_sensor" and dc in DYNAMIC_CLASSES):
        return None
    if dc=="battery":
        return None
    if entity in EXACT:
        return "mdi:"+EXACT[entity]
    name = normalize(key+" "+str(attrs.get("friendly_name","")))
    # Device class is authoritative for measured quantities; name-based
    # refinement is restricted to compatible icons. Combined device names
    # (e.g. temperature_and_humidity_sensor) must not mislabel humidity.
    compatible={
        "temperature":{"thermometer","thermometer-lines","water-thermometer","home-thermometer","snowflake-melt"},
        "power":{"flash","fire"},"energy":{"lightning-bolt","fire"},
        "duration":{"timer-outline"},
    }
    if dc in CLASSES:
        for pattern,icon in RULES:
            if icon in compatible.get(dc,set()) and re.search(pattern,name):
                return "mdi:"+icon
        return "mdi:"+CLASSES[dc]
    for pattern, icon in RULES:
        if re.search(pattern,name):
            return "mdi:"+icon
    if domain in DOMAINS:
        return "mdi:"+DOMAINS[domain]
    return None

def transform(config, states, registry):
    if not isinstance(config,dict) or config.get("strategy") or not isinstance(config.get("views"),list):
        raise RuntimeError("Dashboard is not an editable Lovelace storage dashboard")
    output=copy.deepcopy(config)
    live={s["entity_id"]:s.get("attributes",{}) for s in states}
    entries={r["entity_id"]:r for r in registry}
    changes=[]
    def decorate(row, view):
        ent=row.get("entity")
        if ent not in live or "icon" in row or "image" in row or row.get("show_entity_picture"):
            return row
        icon=icon_for(ent,live[ent],entries.get(ent,{}))
        if icon:
            row["icon"]=icon
            changes.append((view,ent,icon))
        return row
    def visit(card, view):
        if not isinstance(card,dict):
            return
        kind=card.get("type")
        if kind in CARD_TYPES:
            decorate(card,view)
        elif kind in ROW_TYPES and isinstance(card.get("entities"),list):
            for i, row in enumerate(card["entities"]):
                if isinstance(row,str):
                    result=decorate({"entity":row},view)
                    if "icon" in result:
                        card["entities"][i]=result
                elif isinstance(row,dict) and row.get("type") in (None,"simple-entity"):
                    decorate(row,view)
        elif kind in CONTAINERS:
            if isinstance(card.get("cards"),list):
                for child in card["cards"]:
                    visit(child,view)
            if isinstance(card.get("card"),dict):
                visit(card["card"],view)
        # Custom cards, graphs, thermostat, picture elements and unknown
        # schemas are deliberately left as-is, including nested actions.
    for view in output["views"]:
        if not isinstance(view,dict):
            continue
        name=view.get("title") or view.get("path") or "View"
        for card in view.get("cards",[]):
            visit(card,name)
        for section in view.get("sections",[]):
            if isinstance(section,dict):
                for card in section.get("cards",[]):
                    visit(card,name)
    return output,changes

def save_backup(config):
    root=Path(os.environ.get("HA_CONFIG_DIR","/config"))
    if not (root/"configuration.yaml").is_file():
        raise RuntimeError("Run in Home Assistant Terminal, not NanoPi")
    folder=root/"lovelace-backups"
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/("before-icons-"+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")+".json")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        json.dump(config,stream,ensure_ascii=False,indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    return path

def selftest():
    e="sensor.haierpi_twi"
    s="switch.cyrkulacja"
    h="sensor.humidity"
    z="sensor.zamel_moc_chwilowa_kw"
    d="binary_sensor.door"
    live=[{"entity_id":k,"attributes":a} for k,a in [(e,{}),(s,{}),(h,{"device_class":"humidity"}),(z,{"device_class":"power"}),(d,{"device_class":"door"})]]
    config={"views":[{"title":"Pompa","cards":[{"type":"entities","entities":[e,{"entity":s,"name":"Custom","tap_action":{"action":"toggle"}},d,{"entity":h,"icon":"mdi:star"}]}]},{"title":"Energia","sections":[{"cards":[{"type":"grid","cards":[{"type":"tile","entity":z},{"type":"custom:test","entity":e},{"type":"history-graph","entities":[e]}]}]}]}]}
    original=copy.deepcopy(config)
    out,changes=transform(config,live,[])
    assert config==original and len(changes)==3
    rows=out["views"][0]["cards"][0]["entities"]
    assert rows[0]["icon"]=="mdi:water-thermometer"
    assert rows[1]["icon"]=="mdi:water-pump" and rows[1]["tap_action"]=={"action":"toggle"}
    assert rows[2]==d and rows[3]["icon"]=="mdi:star"
    cards=out["views"][1]["sections"][0]["cards"][0]["cards"]
    assert cards[0]["icon"]=="mdi:flash" and cards[1:]==original["views"][1]["sections"][0]["cards"][0]["cards"][1:]
    assert transform(out,live,[])==(out,[])
    assert icon_for(e,{},{"icon":"mdi:star"}) is None
    assert icon_for("sensor.temperature_and_humidity_sensor_5_wilgotnosc",{"device_class":"humidity"},{})=="mdi:water-percent"
    print("SELFTEST OK")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--dashboard",help="Optional Lovelace url_path; default dashboard otherwise")
    args=parser.parse_args()
    if args.self_test:
        selftest()
        return
    if args.apply and args.dry_run:
        parser.error("Choose --apply or --dry-run")
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise RuntimeError("HA Terminal needs Supervisor API permission or HA_TOKEN")
    with urllib.request.urlopen(HELPER,timeout=25) as response:
        source=response.read(40000)
    scope={"__name__":"pinned_ws_helper"}
    exec(compile(source,HELPER,"exec"),scope)
    if os.environ.get("SUPERVISOR_TOKEN"):
        host,port,path="supervisor",80,"/core/websocket"
    else:
        host,port,path=os.environ.get("HA_WS_HOST","homeassistant"),int(os.environ.get("HA_WS_PORT","8123")),"/api/websocket"
    ws=scope["WS"](host,port,path)
    try:
        if ws.recv().get("type")!="auth_required":
            raise RuntimeError("Unexpected authentication handshake")
        ws.send({"type":"auth","access_token":token})
        if ws.recv().get("type")!="auth_ok":
            raise RuntimeError("HA authentication refused")
        kwargs={"url_path":args.dashboard} if args.dashboard else {}
        original=ws.call("lovelace/config",force=True,**kwargs)
        states=ws.call("get_states")
        registry=ws.call("config/entity_registry/list")
        result,changes=transform(original,states,registry)
        for view,entity,icon in changes:
            print(view,"|",entity,"->",icon)
        print(len(changes),"icon changes")
        if not changes:
            print("No changes.")
            return
        if not args.apply:
            print("DRY RUN - nothing saved.")
            return
        if ws.call("lovelace/config",force=True,**kwargs)!=original:
            raise RuntimeError("Dashboard changed concurrently; retry")
        backup=save_backup(original)
        print("Backup:",backup)
        ws.call("lovelace/config/save",config=result,**kwargs)
        if ws.call("lovelace/config",force=True,**kwargs)!=result:
            raise RuntimeError("Save verification failed; backup: "+str(backup))
        print("SUCCESS: dashboard icons updated. No entity IDs or device settings changed.")
    finally:
        ws.close()

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:",exc,file=sys.stderr)
        sys.exit(1)
