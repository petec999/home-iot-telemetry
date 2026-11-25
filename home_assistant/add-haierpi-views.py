#!/usr/bin/env python3
"""Append/refresh FOUR HaierPi views on an EXISTING default Home Assistant dashboard.

Uses the official Lovelace WebSocket API. Does NOT edit .storage files or
configuration.yaml, and does NOT add a second dashboard or restart HA.
Runs from the Home Assistant Terminal/SSH add-on; Python standard library only.

Authentication: SUPERVISOR_TOKEN (add-on with homeassistant_api permission).
Optional HA_TOKEN for a direct HA connection at HA_WS_HOST:HA_WS_PORT.

Backups of the current full dashboard are written to /config/haierpi-lovelace-backups.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import sys
import urllib.request

SOURCE = (
    "https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/"
    "home_assistant/dashboards/haierpi-centrum-1.4.5_1.json"
)
VIEW_PATHS = {
    "haierpi-przeglad",
    "haierpi-cykle",
    "haierpi-obieg",
    "haierpi-bilans",
}

class WS:
    """Small RFC 6455 text-frame client; requires NO third-party Python modules."""
    def __init__(self, host, port, path):
        self.socket = socket.create_connection((host, port), timeout=18)
        self.socket.settimeout(25)
        self.buf = b""
        self.seq = 0
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Connection: Upgrade\r\nUpgrade: websocket\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            data = self.socket.recv(4096)
            if not data:
                raise RuntimeError("WebSocket refused connection")
            response += data
            if len(response) > 16384:
                raise RuntimeError("WebSocket response headers too large")
        header, self.buf = response.split(b"\r\n\r\n", 1)
        status = header.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            raise RuntimeError("HA WebSocket upgrade refused: " + status.decode(errors="replace"))
        accept = base64.b64encode(hashlib.sha1((
            key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if b"sec-websocket-accept: " + accept.lower() not in header.lower():
            raise RuntimeError("HA WebSocket handshake validation failed")

    def close(self):
        self.socket.close()

    def exact(self, n):
        while len(self.buf) < n:
            part = self.socket.recv(max(4096, n - len(self.buf)))
            if not part:
                raise RuntimeError("WebSocket connection closed unexpectedly")
            self.buf += part
        item, self.buf = self.buf[:n], self.buf[n:]
        return item

    def frame(self, op, data):
        mask = os.urandom(4)
        n = len(data)
        header = bytes([0x80 | op])
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", n)
        masked = bytes(b ^ mask[i % 4] for i,b in enumerate(data))
        self.socket.sendall(header + mask + masked)

    def send(self, obj):
        self.frame(1, json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode("utf-8"))

    def recv(self):
        chunks=[]
        while True:
            a,b=self.exact(2)
            op=a & 0x0F
            is_final=bool(a & 0x80)
            masked=bool(b & 0x80)
            size=b & 0x7F
            if size==126: size=struct.unpack("!H",self.exact(2))[0]
            if size==127: size=struct.unpack("!Q",self.exact(8))[0]
            if size>4_000_000:
                raise RuntimeError("WebSocket message too large")
            mask=self.exact(4) if masked else None
            data=self.exact(size)
            if mask is not None:
                data=bytes(ch ^ mask[i%4] for i,ch in enumerate(data))
            if op==8:
                raise RuntimeError("Home Assistant closed WebSocket")
            if op==9:
                self.frame(10,data)
                continue
            if op==10:
                continue
            if op not in (0,1):
                continue
            chunks.append(data)
            if is_final:
                try:
                    return json.loads(b"".join(chunks).decode("utf-8"))
                except (ValueError,UnicodeDecodeError) as exc:
                    raise RuntimeError("Invalid HA WebSocket JSON") from exc

    def call(self, name, **kwargs):
        self.seq+=1
        id=self.seq
        self.send(dict(type=name,id=id,**kwargs))
        while True:
            answer=self.recv()
            if answer.get("type")=="result" and answer.get("id")==id:
                if not answer.get("success"):
                    raise RuntimeError(
                        f"{name} rejected: " + str(answer.get("error",{})))
                return answer["result"]

def get_release_views():
    req=urllib.request.Request(
        SOURCE,headers={"User-Agent":"HaierPi-dashboard-installer/1.4.5_1"})
    with urllib.request.urlopen(req,timeout=25) as response:
        data=response.read(1_000_000)
    artifact=json.loads(data)
    if not isinstance(artifact,dict):
        raise RuntimeError("Dashboard release not an object")
    views=artifact.get("views")
    if not isinstance(views,list) or len(views)!=4:
        raise RuntimeError("Release dashboard must have exactly 4 views")
    paths=[view.get("path") for view in views if isinstance(view,dict)]
    if set(paths)!=VIEW_PATHS or len(paths)!=4:
        raise RuntimeError("Unexpected dashboard paths in release")
    ids=(
      "sensor.haierpi_diagnostics_compressor_starts_today",
      "sensor.haierpi_advanced_diagnostics_co_water_delta_t",
      "sensor.haier_bilans_cop_dobowy",
    )
    raw=json.dumps(artifact)
    if not all(item in raw for item in ids):
        raise RuntimeError("Missing expected real Home Assistant entities")
    print("Downloaded 4 compatible diagnostic views")
    return views

def save_backup(current):
    root=Path(os.environ.get("HA_CONFIG_DIR","/config"))
    if not (root/"configuration.yaml").exists():
        raise RuntimeError("Not in HA Terminal: /config/configuration.yaml is missing")
    backups=root/"haierpi-lovelace-backups"
    backups.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    path=backups/("dashboard-before-1451-"+stamp+"-"+secrets.token_hex(3)+".json")
    # Backup the entire CURRENT config, so other user views are recoverable.
    with path.open("x",encoding="utf-8") as stream:
        json.dump(current,stream,ensure_ascii=False,indent=2)
        stream.write("\n")
    os.chmod(path,0o600)
    return path

def main():
    views=get_release_views()
    token=os.environ.get("SUPERVISOR_TOKEN")
    if token:
        host,port,path="supervisor",80,"/core/websocket"
    else:
        token=os.environ.get("HA_TOKEN")
        host=os.environ.get("HA_WS_HOST","homeassistant")
        port=int(os.environ.get("HA_WS_PORT","8123"))
        path="/api/websocket"
    if not token:
        raise RuntimeError(
          "No SUPERVISOR_TOKEN in HA terminal. The Terminal add-on needs "
          "Home Assistant API permission. Alternatively export HA_TOKEN "
          "(long-lived HA admin token) in the shell, without publishing it.")
    ws=WS(host,port,path)
    try:
        hello=ws.recv()
        if hello.get("type")!="auth_required":
            raise RuntimeError("Unexpected WebSocket authentication handshake")
        ws.send({"type":"auth","access_token":token})
        ack=ws.recv()
        if ack.get("type")!="auth_ok":
            raise RuntimeError("Home Assistant authentication refused or insufficient add-on API access")
        # Omit url_path: HA selects its current DEFAULT dashboard, as in frontend.
        config=ws.call("lovelace/config",force=True)
        if not isinstance(config,dict) or not isinstance(config.get("views"),list):
            raise RuntimeError(
                "Current dashboard is YAML/auto-generated/strategy based. "
                "Refusing to replace it automatically.")
        if config.get("strategy"):
            raise RuntimeError("Generated strategy dashboard: do not replace")
        base=json.loads(json.dumps(config))
        original_views=base["views"]
        for v in original_views:
            if not isinstance(v,dict):
                raise RuntimeError("Unexpected existing dashboard view")
        result=json.loads(json.dumps(base))
        count_added=count_replaced=0
        for new_view in views:
            idx=[i for i,existing in enumerate(result["views"])
                 if existing.get("path")==new_view["path"]]
            if len(idx)>1:
                raise RuntimeError("Duplicate existing view path: "+new_view["path"])
            if idx:
                old=result["views"][idx[0]]
                if old!=new_view:
                    # Only our namespaced paths; preserve ALL other cards/views.
                    result["views"][idx[0]]=new_view
                    count_replaced+=1
            else:
                result["views"].append(new_view)
                count_added+=1
        if result==config:
            print("Already current: 4 HaierPi tabs present; nothing changed.")
            return
        # Detect another UI edit before overwriting the dashboard via its public API.
        check=ws.call("lovelace/config",force=True)
        if check!=config:
            raise RuntimeError("Dashboard changed concurrently. Please retry.")
        backup=save_backup(config)
        print("Backup of the original dashboard:",backup)
        ws.call("lovelace/config/save",config=result)
        verify=ws.call("lovelace/config",force=True)
        if verify!=result:
            raise RuntimeError(
                "Save result differs on reread; backup saved at "+str(backup))
        print(f"SUCCESS: appended {count_added}, updated {count_replaced} HaierPi views.")
        print("Existing views, cards, automations and core services were untouched.")
        print("Refresh your existing Overview dashboard in browser.")
    finally:
        ws.close()

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:",str(exc),file=sys.stderr)
        sys.exit(1)
