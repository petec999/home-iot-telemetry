#!/usr/bin/env python3
import os,json,urllib.request
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
if not token: raise SystemExit("Missing HA API token")
base="http://supervisor/core" if os.environ.get("SUPERVISOR_TOKEN") else os.environ.get("HA_API_URL","http://homeassistant:8123")
def get(path):
    with urllib.request.urlopen(urllib.request.Request(base+path,headers={"Authorization":"Bearer "+token}),timeout=60) as r:
        return json.load(r)
end=datetime.now(timezone.utc)
start=end-timedelta(minutes=5)
for suffix in ("two","twi","tao"):
    for prefix in ("haierpi_","haier_history_"):
        e="sensor."+prefix+suffix
        state=get("/api/states/"+e)
        groups=get("/api/history/period/"+start.isoformat()+"?"+urlencode({"filter_entity_id":e,"end_time":end.isoformat(),"no_attributes":"1"}))
        rows=[r for g in groups for r in g if start<datetime.fromisoformat(r["last_changed"].replace("Z","+00:00"))<=end]
        print(e,"live:",state["state"],"history changes in 5 min:",len(rows))
print("Run at least five minutes after restart. Zero changes may also mean stable temperature; compare repeated checks. No configuration changes.")
