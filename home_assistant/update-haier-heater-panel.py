#!/usr/bin/env python3
"""Add read-only Heater CO status and counters to the existing Pompa ciepła view."""
import copy
import os
import sys
import urllib.request

HELPER = ("https://raw.githubusercontent.com/petec999/home-iot-telemetry/"
          "626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py")
TITLE = "HaierPi · grzałka CO"
HISTORY = "HaierPi · historia grzałki CO (48 h)"
FIELDS = {
    "HaierPi_Heater": ("binary_sensor", "Stan A4A — odczyt pompy", "mdi:heating-coil"),
    "HaierPi_HeaterStartsObserved": ("sensor", "Liczba załączeń", "mdi:counter"),
    "HaierPi_HeaterSecondsObserved": ("sensor", "Łączny obserwowany czas pracy", "mdi:timer-outline"),
}

def resolve(registry, states):
    live = {s["entity_id"] for s in states}
    rows = {}
    devices = set()
    for uid, (domain, name, icon) in FIELDS.items():
        matches = [r for r in registry if r.get("platform") == "mqtt"
                   and r.get("unique_id") == uid and
                   r.get("entity_id","").startswith(domain+".")
                   and not r.get("disabled_by") and r["entity_id"] in live]
        if len(matches) != 1:
            raise RuntimeError("Missing or ambiguous MQTT entity: "+uid+
                               "; install/update HaierPi, verify Discovery, and rerun. No changes.")
        r = matches[0]
        if r.get("device_id"):
            devices.add(r["device_id"])
        rows[uid] = {"entity":r["entity_id"],"name":name,"icon":icon}
    if len(devices) != 1:
        raise RuntimeError("Expected entities of the same HaierPi device")
    return rows

def transform(config, registry, states):
    rows = resolve(registry, states)
    result = copy.deepcopy(config)
    if result.get("strategy") or not isinstance(result.get("views"),list):
        raise RuntimeError("Dashboard is not editable")
    views = [v for v in result["views"] if v.get("path") == "pompa-ciepla"]
    if len(views) != 1:
        raise RuntimeError("Expected one existing Pompa ciepła view")
    view = views[0]
    containers = view.get("sections") or [view]
    for group in containers:
        if not isinstance(group.get("cards"), list):
            raise RuntimeError("Unknown card layout")
        group["cards"] = [c for c in group["cards"] if c.get("title") not in (TITLE,HISTORY)]
    card = {"type":"entities","title":TITLE,"show_header_toggle":False,
            "entities":list(rows.values())}
    graph = {"type":"history-graph","title":HISTORY,"hours_to_show":48,
             "entities":[{"entity":rows["HaierPi_Heater"]["entity"],"name":"A4A"}]}
    cards = containers[0]["cards"]
    insert = next((i+1 for i,c in enumerate(cards) if c.get("title")=="HaierPi · komunikacja MQTT"),0)
    cards[insert:insert]=[card,graph]
    return result

def main():
    token = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise RuntimeError("Run in HA Terminal with Supervisor API permission or HA_TOKEN")
    scope = {"__name__": "pinned_ha_helper"}
    with urllib.request.urlopen(HELPER, timeout=25) as response:
        exec(compile(response.read(40000), HELPER, "exec"), scope)
    if os.environ.get("SUPERVISOR_TOKEN"):
        host, port, path = "supervisor", 80, "/core/websocket"
    else:
        host, port, path = os.environ.get("HA_WS_HOST","homeassistant"), int(os.environ.get("HA_WS_PORT","8123")), "/api/websocket"
    ws = scope["WS"](host,port,path)
    try:
        if ws.recv().get("type") != "auth_required":
            raise RuntimeError("Unexpected HA handshake")
        ws.send({"type":"auth","access_token":token})
        if ws.recv().get("type") != "auth_ok":
            raise RuntimeError("HA authentication failed")
        original = ws.call("lovelace/config", force=True)
        result = transform(original, ws.call("config/entity_registry/list"), ws.call("get_states"))
        if result == original:
            print("Already up to date.")
            return
        if "--dry-run" in sys.argv:
            print("Compatible dashboard; no changes.")
            return
        if ws.call("lovelace/config", force=True) != original:
            raise RuntimeError("Dashboard changed concurrently")
        backup = scope["save_backup"](original)
        print("Backup:", backup)
        ws.call("lovelace/config/save",config=result)
        if ws.call("lovelace/config", force=True) != result:
            raise RuntimeError("Save verification failed; backup: " + str(backup))
        print("SUCCESS: Heater CO read-only status and counters added to Pompa ciepła. Refresh HA.")
    finally:
        ws.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:",exc,file=sys.stderr)
        sys.exit(1)
