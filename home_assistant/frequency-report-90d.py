import os,json,urllib.request
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from collections import defaultdict,Counter
from statistics import median
E=dict(mode="select.haierpi_preset",relay="sensor.haierpi_flrelay",enabled="binary_sensor.haierpi_flimiton",switch="switch.haierpi_flimit_relay",fact="sensor.haierpi_compressor_fact",fset="sensor.haierpi_compressor_fset",defrost="binary_sensor.haierpi_defrost",two="sensor.haier_history_two")
end=datetime.now(timezone.utc)
cursor=end-timedelta(days=90)
rev={v:k for k,v in E.items()}
stats=defaultdict(Counter); requested=defaultdict(Counter); temps=defaultdict(list); indicators=Counter(); high=Counter()
while cursor<end:
    stop=min(cursor+timedelta(days=7),end)
    print("Pobieram",cursor.date(),stop.date(),flush=True)
    url="http://supervisor/core/api/history/period/"+cursor.isoformat()+"?"+urlencode(dict(filter_entity_id=",".join(E.values()),end_time=stop.isoformat()))
    with urllib.request.urlopen(urllib.request.Request(url,headers={"Authorization":"Bearer "+os.environ["SUPERVISOR_TOKEN"]}),timeout=300) as r:
        data=json.load(r)
    events=sorted((datetime.fromisoformat(x["last_changed"].replace("Z","+00:00")),rev[x["entity_id"]],x["state"]) for g in data for x in g)
    state={}; i=0; t=cursor; stable=0; context=None
    while t<stop:
        while i<len(events) and events[i][0]<=t:
            _,k,v=events[i]; state[k]=v; i+=1
        try:
            mode=state["mode"]; relay={"on":1,"off":0}[state["enabled"]]; fact=float(state["fact"]); fset=float(state["fset"])
            valid=mode in ("eco","quiet","turbo") and relay in (0,1) and 0<fact<200 and 0<fset<200 and state["defrost"]=="off" and state["enabled"]==state.get("switch")
        except (KeyError,ValueError,TypeError): valid=False
        if valid:
            key=(mode,int(relay))
            if key!=context: stable=0; context=key
            stable+=1
            if stable>15:
                stats[key][fact]+=1; requested[key][fset]+=1
                ind=(state.get("relay","unknown"),state.get("enabled","unknown"),state.get("switch","unknown"))
                indicators[ind]+=1
                if fact>=60: high[(mode,fact)+ind]+=1
                try:
                    two=float(state["two"])
                    if -10<two<85: temps[(key,fact)].append(two)
                except (KeyError,ValueError,TypeError): pass
        else: stable=0; context=None
        t+=timedelta(minutes=1)
    cursor=stop
for mode in ("eco","quiet","turbo"):
    for relay in (0,1):
        key=(mode,relay); c=stats[key]; print("\n",mode,"FLimit",relay)
        if not c: print("Brak danych"); continue
        total=sum(c.values())
        print("Minuty",total,"Max Fact",max(c),"Max Fset",max(requested[key]))
        for hz,n in c.most_common(15):
            a=temps[(key,hz)]
            print(hz,"Hz",n,"min",round(100*n/total,1),"%","TWO",round(median(a),1) if a else "N/A")
        print("Fset",requested[key].most_common(10))
print("\nflrelay / flimiton / switch / minuty")
for k,n in indicators.most_common(): print(*k,n)
print("\nTryb / Hz / flrelay / flimiton / switch / minuty")
for k,n in high.most_common(50): print(*k,n)
