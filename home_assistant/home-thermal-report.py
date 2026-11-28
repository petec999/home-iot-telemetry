#!/usr/bin/env python3
"""Read-only CWU and heating trend report for HA Terminal."""
import os, json, math, argparse, urllib.request
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from statistics import median

IDS=["sensor.thr316d_ds18b20_temperature","sensor.temperatura_t200","switch.thr316d_ds18b20_on_off_switch","sensor.temperature_and_humidity_sensor_5_temperatura","sensor.haierpi_two","sensor.haierpi_twi","sensor.haierpi_compressor_fact","sensor.haier_bilans_cop_dobowy"]
def number(v):
    try:
        n=float(v)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):
        return None
def points(rows):
    return sorted([(datetime.fromisoformat(r["last_changed"].replace("Z","+00:00")),r["state"]) for r in rows],key=lambda p:p[0])
def analyze(temp,relay,start,end):
    # Only use actual recorded temperature changes; no interpolated endpoints.
    events=sorted([(t,0,v) for t,v in relay]+[(t,1,v) for t,v in temp],key=lambda p:(p[0],p[1]))
    state=None
    prev=None
    rates={"on":[],"off":[]}
    for t,kind,v in events:
        if t>end: break
        if kind==0:
            if v!=state: prev=None
            state=v
        else:
            n=number(v)
            if n is None or state not in rates:
                prev=None
                continue
            if prev is not None and prev[0]>=start:
                dt=(t-prev[0]).total_seconds()/3600
                if 5/60<=dt<=1:
                    rates[state].append((n-prev[1])/dt)
            if prev is None or (t-prev[0]).total_seconds()>=300:
                prev=(t,n)
    return {k:{"samples":len(v),"median_C_per_hour":round(median(v),2) if v else None,"falling_samples":sum(x<0 for x in v),"rising_samples":sum(x>0 for x in v)} for k,v in rates.items()}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--week",action="store_true")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    end=datetime.now(timezone.utc)
    start=end-timedelta(hours=168 if a.week else 24)
    if a.self_test:
        t=start
        assert analyze([(t,"50"),(t+timedelta(minutes=30),"49")],[(t,"off")],start,end)["off"]["median_C_per_hour"]==-2
        assert analyze([(t,"50"),(t+timedelta(minutes=30),"49")],[(t,"off"),(t+timedelta(minutes=15),"on")],start,end)["off"]["samples"]==0
        print("SELFTEST OK")
        return
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token: raise SystemExit("Missing HA API token")
    base="http://supervisor/core" if os.environ.get("SUPERVISOR_TOKEN") else os.environ.get("HA_API_URL","http://homeassistant:8123")
    url=base+"/api/history/period/"+start.isoformat()+"?"+urlencode({"filter_entity_id":",".join(IDS),"end_time":end.isoformat()})
    with urllib.request.urlopen(urllib.request.Request(url,headers={"Authorization":"Bearer "+token}),timeout=90) as r:
        groups=json.load(r)
    data={g[0]["entity_id"]:points(g) for g in groups if g}
    print("CWU: zmiany temperatury przy wlaczonym/wylaczonym przekazniku, C/h")
    for e in IDS[:2]:
        print(e,json.dumps(analyze(data.get(e,[]),data.get(IDS[2],[]),start,end)))
    print("CO: zakres zarejestrowanych wartosci (nie srednia czasowa)")
    for e in IDS[3:]:
        v=[n for t,s in data.get(e,[]) if start<=t<=end and (n:=number(s)) is not None]
        print(e,json.dumps({"samples":len(v),"min":min(v) if v else None,"max":max(v) if v else None}))
    print("Zmiany CWU obejmuja pobor wody, dogrzewanie i straty; nie sa pomiarem strat postojowych. Probki zmian nie sa reprezentatywne czasowo. Przekaznik nie potwierdza przeplywu.")
if __name__=="__main__":
    main()
