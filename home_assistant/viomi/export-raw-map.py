#!/usr/bin/env python3
"""Read cached Robot Vacuum Map diagnostics from HA; save only raw map bytes.
No robot commands, no cloud login, no firmware changes, no secrets printed.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request
import urllib.error
import zlib
from datetime import datetime, timezone

LIMIT=32*1024*1024
HELPER="https://raw.githubusercontent.com/petec999/home-iot-telemetry/626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py"

def summarize(raw):
    result={"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
            "format":"unknown","first_8_bytes_hex":raw[:8].hex()}
    try:
        stream=zlib.decompressobj()
        data=stream.decompress(raw,LIMIT+1)
        if len(data)<=LIMIT and stream.eof:
            result.update(format="zlib",uncompressed_bytes=len(data))
    except zlib.error:
        pass
    return result

def extract(report):
    device=report.get("data",{}).get("device_data",{})
    encoded=device.get("map_data_raw")
    if not isinstance(encoded,str) or not encoded:
        raise ValueError("No map_data_raw in Robot Vacuum Map diagnostics. Check that the live map is available.")
    if len(encoded)>LIMIT:
        raise ValueError("Raw map exceeds size limit")
    raw=base64.b64decode(encoded,validate=True)
    if not raw:
        raise ValueError("Empty raw map")
    return raw,device.get("last_successful_update_timestamp")

def save(raw,floor):
    root=Path("/config")
    if not (root/"configuration.yaml").is_file():
        raise ValueError("Run in Home Assistant Terminal, not HaierPi")
    folder=root/"viomi-map-backups"
    if folder.is_symlink():
        raise ValueError("Unsafe backup directory")
    folder.mkdir(mode=0o700,exist_ok=True)
    os.chmod(folder,0o700)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%fZ")
    path=folder/(floor+"-"+stamp+".bin")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as file:
        file.write(raw)
    return path

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--floor",choices=("parter","pietro","nieprzypisana"),default="nieprzypisana")
    p.add_argument("--map-entity")
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    payload=zlib.compress(b"test map")
    report={"data":{"device_data":{"map_data_raw":base64.b64encode(payload).decode(),"last_successful_update_timestamp":"test"}}}
    assert extract(report)==(payload,"test")
    assert summarize(payload)["uncompressed_bytes"]==8
    if args.self_test:
        print("PASS: raw map extraction and bounded zlib identification")
        return
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise SystemExit("Missing HA API permission in terminal")
    if os.environ.get("SUPERVISOR_TOKEN"):
        host,port,path="supervisor",80,"/core/websocket"
        base="http://supervisor/core/api"
    else:
        host=os.environ.get("HA_WS_HOST","homeassistant")
        port=int(os.environ.get("HA_WS_PORT","8123"))
        path="/api/websocket"
        base=f"http://{host}:{port}/api"
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
        registry=ws.call("config/entity_registry/list")
        candidates=[e for e in registry if e.get("platform")=="robot_vacuum_map"
                    and e.get("config_entry_id") and e.get("entity_id","").startswith(("image.","camera."))
                    and (not args.map_entity or e["entity_id"]==args.map_entity)]
        entries={e["config_entry_id"] for e in candidates}
        if len(entries)!=1:
            raise RuntimeError("Expected one Robot Vacuum Map integration. Specify --map-entity if several exist.")
        entry=entries.pop()
    finally:
        ws.close()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}",entry):
        raise RuntimeError("Invalid config entry ID")
    request=urllib.request.Request(base+"/diagnostics/config_entry/"+entry,
                                   headers={"Authorization":"Bearer "+token})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=60) as response:
        payload=response.read(LIMIT+1)
    if len(payload)>LIMIT:
        raise RuntimeError("Diagnostics exceeded size limit")
    raw,updated=extract(json.loads(payload))
    dest=save(raw,args.floor)
    result=summarize(raw)
    result.update(saved_to=str(dest),floor=args.floor,map_last_download=updated,
                  restore_supported=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    try:
        main()
    except urllib.error.HTTPError as err:
        raise SystemExit(f"HA diagnostics request failed: HTTP {err.code}") from None
    except (ValueError,RuntimeError) as err:
        raise SystemExit(str(err)) from None
