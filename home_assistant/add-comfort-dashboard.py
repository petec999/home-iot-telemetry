#!/usr/bin/env python3
"""Conservative organizer of the existing HA Dom dashboard. Dry run by default."""
from __future__ import annotations
import argparse
import copy
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HELPER=("https://raw.githubusercontent.com/petec999/home-iot-telemetry/"
        "626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py")
HOME="dom-przeglad"
DIAG="dom-diagnostyka"
MARK="HA_HOME_ORGANIZER_V1"
TABS={
    "default_view":("Fotowoltaika i energia","mdi:solar-power"),
    "pompa-ciepla":("Pompa ciepła","mdi:heat-pump"),
    "cwu":("CWU","mdi:water-boiler"),
    "klimatyzacja":("Klimatyzacja","mdi:air-conditioner"),
    "swiatla-rolety":("Światła i rolety","mdi:lightbulb-group"),
    "kamery":("Kamery","mdi:cctv"),
}
# Existing real IDs; no guessed entity creation.
KPIS=[
    ("Temperatura w domu","mdi:home-thermometer",["sensor.temperature_and_humidity_sensor_5_temperatura"]),
    ("Na zewnątrz","mdi:thermometer",["sensor.haierpi_outside_temperature","sensor.haierpi_tao"]),
    ("Produkcja PV teraz","mdi:solar-power",["sensor.sum_produkcja_chwilowa"]),
    ("Produkcja PV dziś","mdi:solar-panel",["sensor.produkcja_pv_suma_dzienna"]),
    ("Pobór pompy ciepła","mdi:flash",["sensor.zamel_moc_chwilowa_kw","sensor.haier_bilans_moc_pradu"]),
    ("COP dobowy (szacunek)","mdi:chart-line",["sensor.haier_bilans_cop_dobowy"]),
    ("Termet T100","mdi:water-thermometer",["sensor.thr316d_ds18b20_temperature"]),
    ("Zasobnik T200","mdi:water-thermometer",["sensor.temperatura_t200"]),
]
PHASE=[
    ("Zasilanie CO","sensor.haierpi_two"),
    ("Powrót CO","sensor.haierpi_twi"),
    ("Temperatura zadana z krzywej","sensor.haierpi_heating_curve_value"),
    ("Sprężarka (Hz)","sensor.haierpi_compressor_fact"),
    ("Odszranianie","binary_sensor.haierpi_defrost"),
    ("Obie pompy CWU – przekaźnik","switch.thr316d_ds18b20_on_off_switch"),
    ("Zasilanie Termeta","switch.zasilanie_piec_gaz_socket_1"),
    ("Zapotrzebowanie CWU (symulacja)","binary_sensor.cwu_zapotrzebowanie_gaz_symulacja"),
]
ERRORS=["sensor.haierpi_active_error"]
CRITICAL={"binary_sensor.haierpi_connected":"off","binary_sensor.backups_stale":"on"}
PROBLEM_CLASSES={"problem","safety","smoke","gas","moisture","carbon_monoxide"}
SAFE_TYPES={"entities","entity","tile","gauge","history-graph","statistics-graph","sensor","markdown","vertical-stack","horizontal-stack","grid"}
REF=re.compile(r"^[a-z_]+\.[a-z0-9_]+$")

def refs(obj):
    out=set()
    if isinstance(obj,dict):
        for k,v in obj.items():
            if k in ("entity","entity_id") and isinstance(v,str) and REF.fullmatch(v):
                out.add(v)
            elif k=="entities" and isinstance(v,list):
                out.update(x for x in v if isinstance(x,str) and REF.fullmatch(x))
            if isinstance(v,(dict,list)):
                out.update(refs(v))
    elif isinstance(obj,list):
        for v in obj:
            out.update(refs(v))
    return out

def allowed(view):
    # Avoid exposing restricted views in the new shared overview.
    return not any(k in view for k in ("visible","strategy","subview")) or (
        view.get("visible",True) is True and not view.get("strategy") and not view.get("subview"))

def tile(entity,name,icon):
    return {"type":"tile","entity":entity,"name":name,"icon":icon,
            "tap_action":{"action":"more-info"},"icon_tap_action":{"action":"more-info"}}

def markdown(title,content):
    return {"type":"markdown","title":title,"content":content}

def grid(cards,columns=2):
    return {"type":"grid","columns":columns,"square":False,"cards":cards}

def nav(name,icon,path,base):
    return {"type":"button","name":name,"icon":icon,"show_state":False,
            "tap_action":{"action":"navigate","navigation_path":"/"+base+"/"+path}}

def safe_move(card):
    if not isinstance(card,dict) or card.get("type") not in SAFE_TYPES:
        return False
    # Retain anything that could provide controls or contain custom UI.
    if any(k in card for k in ("tap_action","hold_action","double_tap_action","visibility","features")):
        return False
    if any(not e.startswith(("sensor.","binary_sensor.")) for e in refs(card)):
        return False
    if card.get("type") in ("grid","vertical-stack","horizontal-stack"):
        return isinstance(card.get("cards"),list) and all(safe_move(c) for c in card["cards"])
    if card.get("type")=="entities":
        for row in card.get("entities",[]):
            if isinstance(row,dict) and (row.get("type") not in (None,"simple-entity","section","divider") or
                    any(k in row for k in ("tap_action","hold_action","double_tap_action","action","service"))):
                return False
    return True

def move_reason(path,card):
    title=str(card.get("title",""))
    if path=="default_view" and title.casefold() in {"growatt inverter","solis inverter"}:
        return "Falowniki – dane szczegółowe"
    if path=="pompa-ciepla":
        if title in {"Haier · obieg chłodniczy i diagnostyka","Diagnostyka obiegu · 6 nowych wskaźników",
                     "Różnica ciśnień czynnika (24 h)","Różnice temperatur obiegu (24 h)",
                     "Licznik rozdzielnica kotłownia"}:
            return "Pompa ciepła – szczegóły techniczne"
        if card.get("type")=="vertical-stack" and any(
                str(c.get("title","")).startswith("Przegrzanie i dochłodzenie")
                for c in card.get("cards",[]) if isinstance(c,dict)):
            return "Pompa ciepła – obieg chłodniczy i wykresy"
    return None

def alarm_content(critical,errors,problems):
    # Jinja evaluates live in HA. Missing readings are not interpreted as OK.
    return (
        "{% set ns = namespace(items=[]) %}\n"
        "{% for id, bad in "+json.dumps(list(critical.items()))+" %}\n"
        "{% set v=states(id) %}\n"
        "{% if v in ['unknown','unavailable'] %}{% set ns.items=ns.items+[(state_attr(id,'friendly_name') or id) ~ ': brak danych'] %}"
        "{% elif v==bad %}{% set ns.items=ns.items+[(state_attr(id,'friendly_name') or id) ~ ': ' ~ v] %}{% endif %}\n"
        "{% endfor %}\n"
        "{% for id in "+json.dumps(errors)+" %}\n"
        "{% set v=states(id) %}"
        "{% if not is_number(v) or v|float(0)!=0 %}{% set ns.items=ns.items+[(state_attr(id,'friendly_name') or id) ~ ': ' ~ v] %}{% endif %}\n"
        "{% endfor %}\n"
        "{% for id in "+json.dumps(problems)+" %}\n"
        "{% if is_state(id,'on') %}{% set ns.items=ns.items+[(state_attr(id,'friendly_name') or id) ~ ': aktywny alarm'] %}"
        "{% elif states(id) in ['unknown','unavailable'] %}{% set ns.items=ns.items+[(state_attr(id,'friendly_name') or id) ~ ': brak danych'] %}{% endif %}\n"
        "{% endfor %}\n"
        "{% if ns.items %}\n"
        "**⚠️ Sprawdź ({{ ns.items|count }}):**\n"
        "{% for item in ns.items %}\n- {{ item }}\n{% endfor %}\n"
        "{% else %}\n**Brak aktywnych ostrzeżeń w monitorowanej grupie.**\n{% endif %}\n\n"
        "_To nie jest pełny system alarmowy. Brak ostrzeżeń nie gwarantuje prawidłowej pracy wszystkich urządzeń._"
    )

def unavailable_content(ids):
    return (
        "{% set ns=namespace(missing=[]) %}\n"
        "{% for id in "+json.dumps(sorted(ids))+" %}\n"
        "{% if states(id) in ['unknown','unavailable'] %}"
        "{% set ns.missing=ns.missing+[(state_attr(id,'friendly_name') or id) ~ ' (' ~ id ~ ')'] %}{% endif %}\n"
        "{% endfor %}\n"
        "**Encje bez odczytu: {{ ns.missing|count }} / "+str(len(ids))+"**\n"
        "{% for item in ns.missing %}\n- {{ item }}\n{% endfor %}\n"
        "_Lista obejmuje encje wskazane w kartach istniejących dostępnych zakładek; niektóre mogą być celowo wyłączone. Brak odczytu nie jest sam w sobie alarmem. Nie sprawdza wieku ostatniej próbki._"
    )

def phase_content(items):
    return "\n".join("- **"+label+":** {{ states('"+e+"') }} {{ state_attr('"+e+"','unit_of_measurement') or '' }}" for label,e in items)+(
        "\n\n_Przekaźnik nie potwierdza fizycznego przepływu. Zapotrzebowanie CWU nie potwierdza pracy palnika._"
    )

def transform(config,states,registry,base="lovelace"):
    if not isinstance(config,dict) or config.get("strategy") or not isinstance(config.get("views"),list):
        raise RuntimeError("Expected editable Lovelace dashboard")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+",base):
        raise RuntimeError("Invalid dashboard URL path")
    views=config["views"]
    if not all(isinstance(v,dict) and isinstance(v.get("path"),str) and v["path"] for v in views):
        raise RuntimeError("Every existing view needs an explicit path; refusing to shift implicit URLs")
    paths=[v["path"] for v in views]
    if HOME in paths or DIAG in paths:
        if paths.count(HOME)==paths.count(DIAG)==1 and MARK in json.dumps(views[paths.index(HOME)],ensure_ascii=False):
            return copy.deepcopy(config),["Already organized; existing edits preserved."]
        raise RuntimeError("Existing view path collision; no changes")
    if len(set(x for x in paths if x is not None))!=len([x for x in paths if x is not None]):
        raise RuntimeError("Duplicate view path")
    output=copy.deepcopy(config)
    live={s["entity_id"]:s.get("attributes",{}) for s in states}
    reg={r["entity_id"]:r for r in registry}
    public=[v for v in output["views"] if isinstance(v,dict) and allowed(v)]
    ids=set().union(*(refs(v) for v in public)) if public else set()
    existing=ids & (set(live)|set(reg))
    # Do not silently include unrelated registry entities or private views.
    critical={e:bad for e,bad in CRITICAL.items() if e in existing}
    errors=[e for e in ERRORS if e in existing]
    problems=sorted(e for e in existing if e.startswith("binary_sensor.") and e not in critical and
                    (live.get(e,{}).get("device_class") or reg.get(e,{}).get("device_class") or reg.get(e,{}).get("original_device_class")) in PROBLEM_CLASSES)
    kpis=[]
    for label,icon,candidates in KPIS:
        e=next((x for x in candidates if x in existing),None)
        if e:
            kpis.append(tile(e,label,icon))
    phases=[(label,e) for label,e in PHASE if e in existing]
    home_cards=[markdown("Dom · przegląd","<!-- "+MARK+" -->\nBieżące wartości z istniejących encji. Szczegóły i sterowanie w zakładkach.")]
    if critical or errors or problems:
        home_cards.append(markdown("Stan instalacji",alarm_content(critical,errors,problems)))
    else:
        home_cards.append(markdown("Stan instalacji","Nie znaleziono znanych encji alarmowych w dostępnych zakładkach."))
    if kpis:
        home_cards.append(grid(kpis))
    if phases:
        home_cards.append(markdown("Ogrzewanie i CWU",phase_content(phases)))
    home_nav=[]
    for path,(name,icon) in TABS.items():
        if any(v.get("path")==path for v in public):
            home_nav.append(nav(name,icon,path,base))
    home_nav.append(nav("Diagnostyka techniczna","mdi:clipboard-pulse",DIAG,base))
    home_cards.append(grid(home_nav))
    tech=[markdown("Dostępność encji",unavailable_content(ids)),
          nav("Powrót do przeglądu","mdi:home",HOME,base)]
    changes=["New overview and technical diagnostics",f"{len(kpis)} KPI, {len(phases)} operating states, {len(ids)} monitored dashboard references"]
    moved=Counter()
    for v in public:
        path=v.get("path")
        if path not in TABS:
            continue
        name,icon=TABS[path]
        v.setdefault("icon",icon)
        if path in ("default_view","swiatla-rolety") and v.get("title") in ("Fotowoltaika","Światła + rolety"):
            v["title"]=name
        if path in ("default_view","pompa-ciepla") and isinstance(v.get("cards"),list):
            kept=[]
            groups={}
            for c in v["cards"]:
                reason=move_reason(path,c) if isinstance(c,dict) else None
                if reason and safe_move(c):
                    groups.setdefault(reason,[]).append(c)
                    moved[json.dumps(c,sort_keys=True,ensure_ascii=False)]+=1
                    changes.append("Moved intact: "+path+" / "+str(c.get("title",reason)))
                else:
                    kept.append(c)
            if groups:
                for reason,cards in groups.items():
                    tech.append(markdown(reason,"Oryginalne karty przeniesione bez zmiany ich zawartości."))
                    tech.extend(cards)
                kept.append(nav("Dane szczegółowe","mdi:clipboard-pulse",DIAG,base))
                v["cards"]=kept
        if path=="kamery":
            cameras=sorted(e for e in refs(v) & existing if e.startswith("camera."))
            if cameras and isinstance(v.get("sections"),list) and v["sections"] and isinstance(v["sections"][0],dict) and isinstance(v["sections"][0].get("cards"),list):
                # Auto uses snapshots unless supported by the frontend; do not force live streams.
                previews=[{"type":"picture-entity","entity":e,"camera_view":"auto","show_name":True,"show_state":False} for e in cameras]
                v["sections"][0]["cards"].insert(0,grid(previews))
                changes.append(f"Added {len(cameras)} camera preview cards; original controls retained")
        if path=="swiatla-rolety":
            for section in v.get("sections",[]):
                if not isinstance(section,dict):
                    continue
                cards=section.get("cards",[])
                names=refs(cards)
                heading=next((c for c in cards if isinstance(c,dict) and c.get("type")=="heading" and c.get("heading")=="Nowa sekcja"),None)
                if heading and names:
                    heading["heading"]="Rolety i pokój chłopców" if any(e.startswith("cover.") for e in names) else "Sceny i oświetlenie pokoi"
    # Preserve the order and paths of all original views. Home is first; existing
    # URLs continue to resolve. All existing cards remain or are moved intact.
    output["views"].insert(0,{"title":"Dom","path":HOME,"icon":"mdi:home","cards":home_cards})
    output["views"].append({"title":"Diagnostyka","path":DIAG,"icon":"mdi:clipboard-pulse","cards":tech})
    if not refs(config)<=refs(output):
        raise RuntimeError("Entity reference preservation check failed")
    actual=Counter(json.dumps(c,sort_keys=True,ensure_ascii=False) for c in tech)
    if any(actual[k]<n for k,n in moved.items()):
        raise RuntimeError("Card preservation check failed")
    return output,changes

def save_backup(config):
    root=Path(os.environ.get("HA_CONFIG_DIR","/config"))
    if not (root/"configuration.yaml").is_file():
        raise RuntimeError("Run in Home Assistant Terminal, not NanoPi")
    folder=root/"lovelace-backups"
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/("before-home-organizer-"+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")+".json")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(config,f,ensure_ascii=False,indent=2)
        f.flush()
        os.fsync(f.fileno())
    return path

def selftest():
    e="sensor.haierpi_compressor_fact"
    t="sensor.temperature_and_humidity_sensor_5_temperatura"
    cam="camera.ogrod_mainstream"
    private="sensor.private"
    detail={"type":"entities","title":"Haier · obieg chłodniczy i diagnostyka","entities":[e]}
    control={"type":"entities","title":"Licznik rozdzielnica kotłownia","entities":["switch.test"]}
    custom={"type":"custom:cwu-weekly-schedule","entity":"schedule.cwu_cyrkulacja"}
    c={"title":"Dom","views":[{"path":"pompa-ciepla","title":"Pompa ciepła","cards":[detail,control,{"type":"entities","entities":[t]}]},
      {"path":"cwu","title":"CWU","cards":[custom]},
      {"path":"kamery","title":"Kamery","sections":[{"type":"grid","cards":[{"type":"entities","entities":[cam]}]}]},
      {"path":"private","title":"Private","visible":[{"user":"abc"}],"cards":[{"type":"entities","entities":[private]}]}]}
    original=copy.deepcopy(c)
    states=[{"entity_id":x,"attributes":{}} for x in [e,t,cam,private,"switch.test","schedule.cwu_cyrkulacja"]]
    result,changes=transform(c,states,[])
    assert c==original and result["views"][0]["path"]==HOME
    assert detail in result["views"][-1]["cards"]
    assert control in result["views"][1]["cards"] and detail not in result["views"][1]["cards"]
    assert result["views"][2]["cards"]==[custom]
    assert result["views"][4]==original["views"][3]
    assert private not in json.dumps(result["views"][0]) and private not in json.dumps(result["views"][-1])
    assert refs(original)<=refs(result)
    assert transform(result,states,[])[0]==result
    assert cam in json.dumps(result["views"][3]["sections"][0]["cards"][0])
    assert not safe_move({"type":"entities","entities":[{"entity":e,"tap_action":{"action":"call-service"}}]})
    assert not safe_move({"type":"custom:foo","entity":e})
    print("SELFTEST OK")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--dry-run",action="store_true")
    mode.add_argument("--restore",type=Path,help="Restore a previously saved dashboard JSON; backs up current config first")
    mode.add_argument("--self-test",action="store_true")
    parser.add_argument("--dashboard",help="Optional dashboard url_path (default: lovelace)")
    args=parser.parse_args()
    if args.self_test:
        selftest()
        return
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:
        raise RuntimeError("HA Terminal needs Supervisor API permission or HA_TOKEN")
    with urllib.request.urlopen(HELPER,timeout=25) as response:
        source=response.read(40000)
    scope={"__name__":"pinned_ws_helper"}
    exec(compile(source,HELPER,"exec"),scope)
    if os.environ.get("SUPERVISOR_TOKEN"):
        host,port,path="supervisor",80,"/core/websocket"
    else:
        host,port,path=os.environ.get("HA_WS_HOST","homeassistant"),int(os.environ.get("HA_WS_PORT","8123")),"/api/websocket"
    ws=scope["WS"](host,port,path)
    try:
        if ws.recv().get("type")!="auth_required":
            raise RuntimeError("Unexpected authentication handshake")
        ws.send({"type":"auth","access_token":token})
        if ws.recv().get("type")!="auth_ok":
            raise RuntimeError("HA authentication refused")
        kwargs={"url_path":args.dashboard} if args.dashboard else {}
        original=ws.call("lovelace/config",force=True,**kwargs)
        if args.restore:
            with args.restore.open(encoding="utf-8") as f:
                result=json.load(f)
            if not isinstance(result,dict) or not isinstance(result.get("views"),list):
                raise RuntimeError("Invalid dashboard backup")
            changes=["Restore "+str(args.restore)]
        else:
            result,changes=transform(original,ws.call("get_states"),ws.call("config/entity_registry/list"),args.dashboard or "lovelace")
        for change in changes:
            print(change)
        if result==original:
            print("No changes.")
            return
        if not (args.apply or args.restore):
            print("DRY RUN - nothing saved.")
            return
        if ws.call("lovelace/config",force=True,**kwargs)!=original:
            raise RuntimeError("Dashboard changed concurrently; retry")
        backup=save_backup(original)
        print("Backup:",backup)
        ws.call("lovelace/config/save",config=result,**kwargs)
        if ws.call("lovelace/config",force=True,**kwargs)!=result:
            raise RuntimeError("Verification failed; restore using backup: "+str(backup))
        print("SUCCESS: dashboard saved and verified. Device settings unchanged.")
    finally:
        ws.close()


TITLE="Komfort cieplny i dostępność telemetrii"
def transform(config,states,registry,base="lovelace"):
    out=copy.deepcopy(config)
    views=[v for v in out["views"] if v.get("path")==DIAG]
    if len(views)!=1 or not isinstance(views[0].get("cards"),list): raise RuntimeError("Missing diagnostics cards view")
    rows=[]
    for h,label in [(24,"24 h"),(168,"7 dni")]:
        rows.append({"type":"section","label":label})
        for k,name in [("comfort_in_range","Komfort 20–22°C"),("comfort_below","Poniżej 20°C"),("comfort_above","Powyżej 22°C"),("telemetry_missing","Brak odczytu Haier")]:
            rows.append({"entity":f"sensor.ha_heat_{k}_{h}h_percent","name":name})
    live={s["entity_id"] for s in states}
    if not {r["entity"] for r in rows if "entity" in r}<=live: raise RuntimeError("Missing comfort statistics")
    card={"type":"entities","title":TITLE,"show_header_toggle":False,"entities":rows,"footer":{"type":"buttons","entities":[]}}
    card.pop("footer")
    note={"type":"markdown","title":"Interpretacja statystyk komfortu","content":"Pełne okna po 24 h i 7 dniach od instalacji. Brak historii może zaniżać procenty. Dostępność dotyczy stanów sprężarki i odszraniania, nie wieku danych."}
    cards=views[0]["cards"]
    cards[:]=[c for c in cards if c.get("title") not in (TITLE,note["title"])]
    cards.extend([card,note])
    return out,["Updated comfort statistics in existing diagnostics view"]
def selftest():
    states=[{"entity_id":f"sensor.ha_heat_{k}_{h}h_percent"} for k in ("comfort_in_range","comfort_below","comfort_above","telemetry_missing") for h in (24,168)]
    c={"views":[{"path":DIAG,"cards":[{"type":"markdown","content":"keep"}]}]}
    out,_=transform(c,states,[])
    assert len(out["views"][0]["cards"])==3
    assert transform(out,states,[])[0]==out
    print("SELFTEST OK")
if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("ERROR:",exc,file=sys.stderr); sys.exit(1)
