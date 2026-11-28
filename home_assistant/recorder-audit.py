#!/usr/bin/env python3
import os,json,urllib.request,math
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from collections import Counter
token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
if not token: raise SystemExit("Missing HA API token")
base="http://supervisor/core" if os.environ.get("SUPERVISOR_TOKEN") else os.environ.get("HA_API_URL","http://homeassistant:8123")
end=datetime.now(timezone.utc)
start=end-timedelta(hours=2)
for e in ["sensor.haierpi_two","sensor.haierpi_twi","sensor.haierpi_tao"]:
    url=base+"/api/history/period/"+start.isoformat()+"?"+urlencode({"filter_entity_id":e,"end_time":end.isoformat(),"no_attributes":"1"})
    with urllib.request.urlopen(urllib.request.Request(url,headers={"Authorization":"Bearer "+token}),timeout=60) as r:
        groups=json.load(r)
    rows=groups[0] if groups else []
    values=[]
    for row in rows:
        try:
            v=float(row["state"])
            values.append(v if math.isfinite(v) else None)
        except (ValueError,TypeError):
            values.append(None)
    print(e,"records",len(rows),"examples",Counter(r["state"] for r in rows).most_common(8))
    for digits in (2,1,0):
        rounded=[round(v,digits) if v is not None else None for v in values]
        changes=sum(a!=b for a,b in zip(rounded,rounded[1:]))
        print("precision",digits,"estimated state transitions",changes,"reduction percent",round(100*(1-changes/max(1,len(rows)-1)),1))
    print("Non-numeric records",sum(v is None for v in values))
print("Read-only estimate; rounding does not guarantee recorder reduction, especially if attributes change.")
