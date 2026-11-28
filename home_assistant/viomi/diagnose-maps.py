#!/usr/bin/env python3
"""Read-only Viomi V8 map diagnostics via the installed local HA integration."""
import argparse
import json
import os
import urllib.request

HELPER="https://raw.githubusercontent.com/petec999/home-iot-telemetry/626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vacuum",default="vacuum.viomi_v8_local")
    a=p.parse_args()
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise SystemExit("Run in Home Assistant Terminal with HA API permission")
    if os.environ.get("SUPERVISOR_TOKEN"):
        host,port,path="supervisor",80,"/core/websocket"
    else:
        host,port,path=os.environ.get("HA_WS_HOST","homeassistant"),int(os.environ.get("HA_WS_PORT","8123")),"/api/websocket"
    with urllib.request.urlopen(HELPER,timeout=25) as f:
        source=f.read(200000)
    scope={"__name__":"helper"}
    exec(compile(source,HELPER,"exec"),scope)
    ws=scope["WS"](host,port,path)
    try:
        if ws.recv().get("type")!="auth_required":
            raise RuntimeError("Unexpected authentication handshake")
        ws.send({"type":"auth","access_token":token})
        if ws.recv().get("type")!="auth_ok":
            raise RuntimeError("Authentication failed")
        ws.socket.settimeout(180)
        report=ws.call("xiaomi_viomi/map_diagnostics",entity_id=a.vacuum)
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        ws.close()

if __name__=="__main__":
    main()
