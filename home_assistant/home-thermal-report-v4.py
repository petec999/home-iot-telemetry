#!/usr/bin/env python3
"""Read-only CWU and heating trend report for HA Terminal."""
import os, json, math, argparse, urllib.request
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from statistics import median

IDS=["sensor.thr316d_ds18b20_temperature","sensor.temperatura_t200","switch.thr316d_ds18b20_on_off_switch","sensor.temperature_and_humidity_sensor_5_temperatura","sensor.haier_history_two","sensor.haier_history_twi","sensor.haierpi_compressor_fact","sensor.haier_bilans_cop_dobowy"]
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
from bisect import bisect_right
from zoneinfo import ZoneInfo
def series(rows):
    ts=[t for t,v in rows]; vs=[v for t,v in rows]
    def at(t):
        i=bisect_right(ts,t)-1
        return vs[i] if i>=0 else None
    return at
def stats(v):
    return {"n":len(v),"median":round(median(v),2) if v else None,"min":round(min(v),2) if v else None,"max":round(max(v),2) if v else None}
def cycles(rows,start,end):
    prev=None; opened=None
    for t,v in rows:
        if t<=start:
            prev=v; continue
        if t>=end: break
        if v==prev: continue
        if prev=="off" and v=="on": opened=t
        elif prev=="on" and v=="off" and opened is not None:
            yield opened,t
            opened=None
        else: opened=None
        prev=v
def report(data,start,end):
    get=lambda e: series(data.get(e,[]))
    t100,t200,relay,room,two,twi,comp,cop=map(get,IDS[:8])
    frost=get("binary_sensor.haierpi_defrost")
    runs=list(cycles(data.get(IDS[2],[]),start,end))
    print("Pelne cykle cyrkulacji:",len(runs),"czas min:",stats([(b-a).total_seconds()/60 for a,b in runs]))
    for name,f in [("T100",t100),("T200",t200)]:
        vals=[]
        for a,b in runs:
            x,y=number(f(a)),number(f(b))
            if x is not None and y is not None: vals.append(y-x)
        print(name,"zmiana C na cykl:",stats(vals),"bez wzrostu:",sum(v<=0 for v in vals))
    comfort=[0,0,0,0]; delta=[]; night=[[],[]]; daily={}
    tz=ZoneInfo("Europe/Warsaw")
    t=start
    while t<end:
        nxt=min(t+timedelta(minutes=5),end)
        mins=(nxt-t).total_seconds()/60
        r=number(room(t))
        comfort[3 if r is None else 0 if r<20 else 1 if r<=22 else 2]+=mins
        c,x,y=number(comp(t)),number(two(t)),number(twi(t))
        if c is not None and c>0 and frost(t)=="off" and x is not None and y is not None:
            delta.append(x-y)
        local=t.astimezone(tz)
        if 1<=local.hour<5 and relay(t)=="off":
            for i,f in enumerate((t100,t200)):
                a,b=number(f(t)),number(f(nxt))
                if a is not None and b is not None and relay(nxt)=="off":
                    # Reject any relay transition inside the interval.
                    if not any(t<u<nxt and v!="off" for u,v in data.get(IDS[2],[])):
                        night[i].append((b-a)*60/mins)
        t=nxt
    print("Komfort, % calego okna (<20 / 20-22 / >22 / brak):",[round(100*x/sum(comfort),1) for x in comfort])
    print("Delta T przy aktywnej sprezarce bez defrostu, C:",stats(delta))
    for name,v in zip(("T100","T200"),night): print(name,"nocne zmiany C/h (01-05, pompy off):",stats(v))
    for t,v in data.get(IDS[7],[]):
        if start<=t<=end and number(v) is not None:
            daily[t.astimezone(tz).date()]=(t,number(v))
    print("COP: ostatni zapis zakonczonych lokalnych dob (tylko pelne doby):")
    for day,(t,v) in sorted(daily.items()):
        if start.astimezone(tz).date()<day<end.astimezone(tz).date():
            print(day,v,"ostatni zapis",t.astimezone(tz).strftime("%H:%M"))
    print("Liczba rekordow zwroconych przez API (nie rozmiar bazy):")
    for e,rows in data.items(): print(e,len(rows))
    print("Ograniczenia: probkowanie 5 min, ostatni znany stan nie dowodzi swiezosci; nocne zmiany nie sa czystymi stratami. Delta T nie potwierdza trybu CO. COP to ostatni zapis, nie gwarantowany wynik koncowy.")
def extended(data,start,end):
    runs=list(cycles(data.get(IDS[2],[]),start,end))
    print("Cykle wedlug czasu: <1min / 1-5min / 5-15min / >=15min")
    buckets=[[],[],[],[]]
    f=series(data.get(IDS[1],[]))
    relayrows=data.get(IDS[2],[])
    for a,b in runs:
        m=(b-a).total_seconds()/60
        k=0 if m<1 else 1 if m<5 else 2 if m<15 else 3
        buckets[k].append((a,b))
    for label,group in zip(("<1","1-5","5-15",">=15"),buckets):
        direct=[]; delayed=[]
        for a,b in group:
            x,y=number(f(a)),number(f(b))
            if x is not None and y is not None: direct.append(y-x)
            c=b+timedelta(minutes=5)
            if c>end or any(b<t<=c and v!="off" for t,v in relayrows): continue
            z=number(f(c))
            if x is not None and z is not None: delayed.append(z-x)
        print(label,"liczba",len(group),"T200 na koncu",stats(direct),"T200 po 5min",stats(delayed),"wzrost po 5min",sum(v>0 for v in delayed))
    print("Powtarzalnosc rekordow (kolejne identyczne stany, nie dowod zbednego zapisu):")
    for e in IDS[4:6]:
        rows=data.get(e,[])
        same=sum(a[1]==b[1] for a,b in zip(rows,rows[1:]))
        print(e,"rekordy",len(rows),"identyczne",same,"procent",round(100*same/max(1,len(rows)-1),1))
    outdoor=next((e for e in OUTSIDE if any(number(v) is not None for t,v in data.get(e,[]))),None)
    if outdoor:
        f=series(data[outdoor]); tz=ZoneInfo("Europe/Warsaw"); weather={}; last={}
        t=start
        while t<end:
            n=number(f(t)); day=t.astimezone(tz).date()
            if n is not None: weather.setdefault(day,[]).append(n)
            t+=timedelta(minutes=5)
        for t,v in data.get(IDS[7],[]):
            if start<=t<=end and number(v) is not None: last[t.astimezone(tz).date()]=number(v)
        print("COP i pogoda (mediana temperatury z probek 5min):")
        for day in sorted(last):
            if start.astimezone(tz).date()<day<end.astimezone(tz).date():
                print(day,"COP",last[day],"temp",stats(weather.get(day,[])))
    else: print("Brak historii temperatury zewnetrznej")
    print("Opozniona zmiana T200 nie dowodzi przeplywu; brak kolejnego wlaczenia nie wyklucza poboru ani dogrzewania. Nie zmieniono Recorder.")
OUTSIDE=["sensor.haierpi_outside_temperature","sensor.haier_history_tao"]
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--week",action="store_true")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    end=datetime.now(timezone.utc); start=end-timedelta(hours=168 if a.week else 24)
    if a.self_test:
        t=start+timedelta(minutes=10)
        assert list(cycles([(start,"off"),(t,"on"),(t+timedelta(minutes=10),"off")],start,end))==[(t,t+timedelta(minutes=10))]
        assert series([(t,"42")])(start) is None
        assert series([(t,"42")])(t)=="42"
        print("SELFTEST OK"); return
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token: raise SystemExit("Missing HA API token")
    base="http://supervisor/core" if os.environ.get("SUPERVISOR_TOKEN") else os.environ.get("HA_API_URL","http://homeassistant:8123")
    data={}
    for e in IDS+["binary_sensor.haierpi_defrost"]+OUTSIDE:
        url=base+"/api/history/period/"+start.isoformat()+"?"+urlencode({"filter_entity_id":e,"end_time":end.isoformat(),"no_attributes":"1"})
        with urllib.request.urlopen(urllib.request.Request(url,headers={"Authorization":"Bearer "+token}),timeout=120) as r:
            groups=json.load(r)
        data[e]=points(groups[0]) if groups and groups[0] else []
    print("Historia TWO/TWI/TAO: nowe encje, okres przed instalacja moze nie miec danych.")
    report(data,start,end)
    extended(data,start,end)
if __name__=="__main__":
    main()
