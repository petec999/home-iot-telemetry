#!/usr/bin/env python3
"""Read-only rolling 24-hour report. Run in HA Terminal."""
import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

ENTITIES = {
    "sensor.haierpi_compressor_fact": ("Sprezarka", "frequency"),
    "binary_sensor.haierpi_defrost": ("Odszranianie", "binary"),
    "switch.thr316d_ds18b20_on_off_switch": ("Przekaznik cyrkulacji", "binary"),
    "switch.zasilanie_piec_gaz_socket_1": ("Zasilanie Termeta", "binary"),
}
def active(value, kind):
    if kind == "binary":
        return {"on": True, "off": False}.get(value)
    try:
        n = float(value)
        return n > 0 if 0 <= n < 1000 else None
    except (ValueError, TypeError):
        return None

def summarize(rows, start, end, kind):
    points = sorted((datetime.fromisoformat(r["last_changed"].replace("Z","+00:00")), active(r["state"],kind)) for r in rows)
    state = None
    cursor = start
    seconds = known = 0
    starts = 0
    for t, new in points:
        if t <= start:
            state = new
            continue
        if t >= end:
            break
        dt = (t-cursor).total_seconds()
        if state is not None:
            known += dt
            if state:
                seconds += dt
        if state is False and new is True:
            starts += 1
        cursor, state = t, new
    dt = (end-cursor).total_seconds()
    if state is not None:
        known += dt
        if state:
            seconds += dt
    return {"starts_observed":starts,"active_minutes":round(seconds/60,1),"coverage_percent":round(100*known/(end-start).total_seconds(),1)}


def cycle_details(rows, start, end, kind):
    from statistics import mean, median
    points = sorted((datetime.fromisoformat(r["last_changed"].replace("Z","+00:00")), active(r["state"],kind)) for r in rows)
    state, began = None, None
    runs, stops = [], []
    for t, new in points:
        if t <= start:
            state, began = new, None
            continue
        if t >= end:
            break
        if new == state:
            continue
        if began is not None and new is not None and state is not None:
            (runs if state else stops).append((t-began).total_seconds()/60)
        began = t if state is not None and new is not None else None
        state = new
    def stats(values):
        return {"count":len(values),"min":round(min(values),1),"mean":round(mean(values),1),"median":round(median(values),1),"max":round(max(values),1)} if values else {"count":0}
    return {"complete_runs_minutes":stats(runs),"complete_stops_minutes":stats(stops),"runs_under_5min":sum(v<5 for v in runs),"runs_under_10min":sum(v<10 for v in runs)}


def main():
    import sys
    if "--self-test" in sys.argv:
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[{"last_changed":(start+timedelta(minutes=m)).isoformat(),"state":s} for m,s in [(0,"off"),(10,"on"),(30,"off"),(40,"unavailable")]]
        assert summarize(rows,start,start+timedelta(hours=1),"binary")=={"starts_observed":1,"active_minutes":20.0,"coverage_percent":66.7}
        assert cycle_details(rows,start,start+timedelta(hours=1),"binary")["complete_runs_minutes"]["mean"] == 20.0
        assert cycle_details(rows,start,start+timedelta(hours=1),"binary")["complete_stops_minutes"]["count"] == 0
        print("SELFTEST OK")
        return
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise SystemExit("Missing HA API token")
    base="http://supervisor/core" if os.environ.get("SUPERVISOR_TOKEN") else os.environ.get("HA_API_URL","http://homeassistant:8123")
    end=datetime.now(timezone.utc)
    start=end-timedelta(hours=24)
    from urllib.parse import urlencode
    url=base+"/api/history/period/"+start.isoformat()+"?"+urlencode({"filter_entity_id":",".join(ENTITIES),"end_time":end.isoformat()})
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token})
    with urllib.request.urlopen(req,timeout=60) as response:
        groups=json.load(response)
    indexed={g[0]["entity_id"]:g for g in groups if g}
    print("Ostatnie 24 h; czasy i cykle obserwowane, nie estymowane.")
    for entity,(name,kind) in ENTITIES.items():
        result=summarize(indexed.get(entity,[]),start,end,kind)
        print(name+": "+json.dumps(result,ensure_ascii=False))
        print("  Pelne cykle: "+json.dumps(cycle_details(indexed.get(entity,[]),start,end,kind),ensure_ascii=False))
    print("Przekazniki nie potwierdzaja przeplywu ani pracy palnika. Pokrycie oznacza znany stan w historii, nie swiezosc probek.")

if __name__=="__main__":
    main()
