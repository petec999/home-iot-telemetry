#!/usr/bin/env python3
"""Add one MQTT health card to the existing Pompa ciepła view."""
import copy
import os
import sys
import urllib.request

HELPER = ("https://raw.githubusercontent.com/petec999/home-iot-telemetry/"
          "626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py")
ENTITY = "sensor.haierpi_mqtt_heartbeat"
TITLE = "HaierPi · komunikacja MQTT"
CARD = {"type": "markdown", "title": TITLE, "content": """{% set e = states.sensor.haierpi_mqtt_heartbeat %}
{% if e is not defined or e.state in ['unknown', 'unavailable'] %}
**🔴 Brak aktualnego heartbeat MQTT**
{% else %}
{% set age = (as_timestamp(now()) - as_timestamp(e.last_changed)) | int %}
{% if age >= 180 %}
**🔴 Awaria komunikacji**
{% elif age >= 90 %}
**🟠 Brak świeżego potwierdzenia**
{% else %}
**🟢 HA odbiera heartbeat MQTT**
{% endif %}

Ostatni odbiór: {{ age }} s temu ({{ as_local(e.last_changed).strftime('%H:%M:%S') }}).
{% endif %}

Kontrola odbioru MQTT; nie zastępuje diagnostyki Modbus."""}

def transform(config):
    result = copy.deepcopy(config)
    if result.get("strategy"):
        raise RuntimeError("Dashboard uses strategy")
    views = [v for v in result["views"] if v.get("path") == "pompa-ciepla"]
    if len(views) != 1:
        raise RuntimeError("Expected one existing Pompa ciepła view")
    view = views[0]
    containers = view.get("sections") or [view]
    for group in containers:
        if not isinstance(group.get("cards"), list):
            raise RuntimeError("Unknown card layout")
        group["cards"] = [c for c in group["cards"] if c.get("title") != TITLE]
    containers[0]["cards"].insert(0, copy.deepcopy(CARD))
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
        if ENTITY not in {s["entity_id"] for s in ws.call("get_states")}:
            raise RuntimeError("Heartbeat sensor missing; verify entity ID before dashboard update")
        original = ws.call("lovelace/config", force=True)
        result = transform(original)
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
        print("SUCCESS: MQTT health card added to Pompa ciepła only.")
    finally:
        ws.close()

if __name__ == "__main__":
    main()
