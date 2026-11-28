#!/usr/bin/env python3
"""Add/update only our Odkurzacz Lovelace view. No credentials in source."""
import argparse, copy, json, os, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HELPER="https://raw.githubusercontent.com/petec999/home-iot-telemetry/626ae2ed0814cd77bfc86e7a2e741ba9db8aff0f/home_assistant/add-haierpi-views.py"
MARK="VIOMI_DASHBOARD_V1"
VIEW="odkurzacz"
FLOORS=(("Parter","parter"),("Piętro","pietro"))
KEYS={
 "battery_level":("Bateria","mdi:battery"),"cleaning_time":("Czas sprzątania","mdi:timer-outline"),
 "cleaned_area":("Powierzchnia","mdi:floor-plan"),"water_grade":("Dozowanie wody","mdi:water"),
 "bin_type":("Pojemnik","mdi:delete-outline"),"cleaning_mode":("Tryb pracy","mdi:robot-vacuum"),
 "mop_attached":("Mop założony","mdi:water-check"),"mop_route":("Trasa mopowania","mdi:routes"),
 "repeat_cleaning":("Podwójne sprzątanie","mdi:repeat"),"voice_volume":("Głośność","mdi:volume-high"),
 "charging":("Ładowanie","mdi:battery-charging"),"do_not_disturb":("Nie przeszkadzać","mdi:weather-night"),
 "map_id":("ID aktywnej mapy","mdi:map-marker"),"map_count":("Liczba map","mdi:layers"),
 "has_map":("Mapa dostępna","mdi:map-check"),"remember_map":("Zapamiętywanie mapy","mdi:content-save"),
 "position_x":("Pozycja X","mdi:axis-x-arrow"),"position_y":("Pozycja Y","mdi:axis-y-arrow"),
 "position_heading":("Kierunek","mdi:compass"),"error_code":("Kod błędu","mdi:alert-circle-outline"),
}
CONSUMABLES=(("main_brush","Szczotka główna"),("side_brush","Szczotka boczna"),("filter","Filtr"),("mop","Mop"))
def tile(e,n,i):
    return {"type":"tile","entity":e,"name":n,"icon":i,"tap_action":{"action":"more-info"}}
def grid(cards,columns=2):
    return {"type":"grid","columns":columns,"square":False,"cards":cards}
def md(t,c):
    return {"type":"markdown","title":t,"content":c}
def action(n,i,service,data,confirmation=None):
    tap={"action":"perform-action","perform_action":service,"data":data}
    if confirmation: tap["confirmation"]={"text":confirmation}
    return {"type":"button","name":n,"icon":i,"show_state":False,"tap_action":tap}
def identify(states,registry,vac_arg=None,cam_arg=None):
    live={x["entity_id"]:x for x in states}
    local=[r for r in registry if r.get("platform")=="xiaomi_viomi" and r["entity_id"].startswith("vacuum.") and r["entity_id"] in live]
    if vac_arg:
        local=[r for r in local if r["entity_id"]==vac_arg]
    if len(local)!=1: raise RuntimeError("Need exactly one live Viomi local vacuum; use --vacuum if multiple")
    robot=local[0]; uid=str(robot.get("unique_id") or "")
    dev=robot.get("device_id")
    sensors={}
    for r in registry:
        e=r["entity_id"]; u=str(r.get("unique_id") or "")
        if r.get("platform")=="xiaomi_viomi" and e.startswith("sensor.") and e in live and uid and u.startswith(uid+"_"):
            sensors[u[len(uid)+1:]]=e
    cameras=[r["entity_id"] for r in registry if r.get("platform") in ("robot_vacuum_map","xiaomi_cloud_map_extractor") and r["entity_id"].startswith("camera.") and r["entity_id"] in live]
    if cam_arg:
        if cam_arg not in cameras: raise RuntimeError("Specified camera is not a detected vacuum map camera")
        cameras=[cam_arg]
    if len(cameras)>1: raise RuntimeError("Multiple map cameras; use --camera")
    cam=cameras[0] if cameras else None
    return robot["entity_id"],sensors,cam,live[robot["entity_id"]]["attributes"]
def build_view(vac,sensors,cam,attrs,media):
    def group(keys):
        return [tile(sensors[k],*KEYS[k]) for k in keys if k in sensors]
    cards=[md("Viomi V8 Local","<!-- "+MARK+" -->\nSterowanie lokalne · zapisane plany dwóch kondygnacji."),
           tile(vac,"Odkurzacz","mdi:robot-vacuum")]
    buttons=[]
    for n,i,s in (("Start","mdi:play","start"),("Pauza","mdi:pause","pause"),("Stop","mdi:stop","stop"),("Baza","mdi:home-map-marker","return_to_base")):
        buttons.append(action(n,i,"vacuum."+s,{"entity_id":vac}))
    cards.append(grid(buttons,4))
    speeds=attrs.get("fan_speed_list",[])
    if speeds:
        cards.append(md("Siła ssania","Aktualnie: **{{ state_attr('"+vac+"','fan_speed') or 'Brak danych' }}**"))
        cards.append(grid([action({"Silent":"Cicho","Standard":"Standard","Medium":"Średnio","Turbo":"Turbo"}.get(s,s),"mdi:fan","vacuum.set_fan_speed",{"entity_id":vac,"fan_speed":s}) for s in speeds if s in ("Silent","Standard","Medium","Turbo")],4))
    overview=group(("battery_level","cleaning_time","cleaned_area","charging"))
    if overview: cards.append(grid(overview))
    maps=[md("Mapy domu","Mapa aktywna pochodzi z odkurzacza. Zapisane obrazy parteru i piętra to kopie, nie aktywne plany nawigacji. Zapisuj każdy plan dopiero po sprawdzeniu obrazu.")]
    if cam:
        maps.append({"type":"picture-entity","entity":cam,"name":"Mapa aktywna","show_state":False,"camera_view":"auto"})
        if media:
            maps.append(grid([action("Zapisz "+n.lower(),"mdi:content-save","camera.snapshot",{"entity_id":cam,"filename":"/media/viomi/"+f+".png"},"Czy aktywna mapa przedstawia "+n.lower()+"? Nadpiszesz zapisaną kopię.") for n,f in FLOORS]))
    else:
        maps.append(md("Mapa aktywna","Dodaj integrację Robot Vacuum Map. Następnie uruchom instalator panelu ponownie."))
    if media:
        for n,f in FLOORS:
            maps.append(md(n,"Obraz zapisany w Media → Moje media → viomi/"+f+".png. Jeśli zmienisz obraz, odśwież przeglądarkę."))
            maps.append({"type":"picture","image":"media-source://media_source/local/viomi/"+f+".png","tap_action":{"action":"none"},"hold_action":{"action":"none"}})
        maps.append(md("Własne plany","Możesz też wgrać obrazy PNG przez Media / udział sieciowy do katalogu viomi. Brak pliku oznacza, że plan nie został jeszcze zapisany."))
    else:
        maps.append(md("Zapis map","Katalog /media nie jest dostępny lub dozwolony. Udostępnij katalog Media w Terminalu i ponów instalację."))
    cards.append({"type":"vertical-stack","cards":maps})
    settings=group(("water_grade","bin_type","cleaning_mode","mop_attached","mop_route","repeat_cleaning","voice_volume","do_not_disturb"))
    if settings:
        cards.extend([md("Mopowanie i ustawienia","Odczyt lokalny. Regulacja wody nie jest jeszcze zweryfikowana."),grid(settings)])
    service=[]
    for key,n in CONSUMABLES:
        e=sensors.get(key+"_remaining_pct")
        if e: service.append({"type":"gauge","entity":e,"name":n,"min":0,"max":100,"severity":{"red":0,"yellow":15,"green":35}})
    if service: cards.extend([md("Eksploatacja","Pozostały czas według nominalnych liczników producenta; 0% nie jest diagnozą uszkodzenia."),grid(service)])
    details=[]
    for key,n in CONSUMABLES:
        for suffix,desc in (("_used","praca"),("_left","pozostało")):
            if key+suffix in sensors: details.append({"entity":sensors[key+suffix],"name":n+" – "+desc})
    if details: cards.append({"type":"entities","title":"Liczniki godzin","entities":details})
    diag=group(("map_id","map_count","has_map","remember_map","position_x","position_y","position_heading","error_code"))
    if diag: cards.extend([md("Diagnostyka map i robota","Współrzędne są surowe, nie służą do wyznaczania stref na obrazach."),grid(diag)])
    history=[sensors[k] for k in ("battery_level","cleaning_time","cleaned_area") if k in sensors]
    cards.append({"type":"history-graph","title":"Historia pracy (48 h)","hours_to_show":48,"entities":[vac]+history})
    return {"title":"Odkurzacz","path":VIEW,"icon":"mdi:robot-vacuum","cards":cards}
def transform(original,view):
    if not isinstance(original,dict) or not isinstance(original.get("views"),list) or original.get("strategy"):
        raise RuntimeError("Expected editable Lovelace dashboard")
    out=copy.deepcopy(original)
    hits=[i for i,v in enumerate(out["views"]) if v.get("path")==VIEW]
    if hits:
        if len(hits)!=1 or MARK not in json.dumps(out["views"][hits[0]],ensure_ascii=False):
            raise RuntimeError("Existing unrelated Odkurzacz tab; refusing overwrite")
        out["views"][hits[0]]=view
    else:
        out["views"].append(view)
    return out
def backup(original):
    root=Path("/config/lovelace-backups")
    root.mkdir(exist_ok=True)
    file=root/("before-viomi-"+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")+".json")
    fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f: json.dump(original,f,ensure_ascii=False,indent=2)
    return file
def selftest():
    v="vacuum.viomi_v8_local"; c="camera.viomi_map"; e="sensor.viomi_v8_local_battery"
    states=[{"entity_id":v,"attributes":{"fan_speed_list":["Turbo"]}},{"entity_id":c,"attributes":{}},{"entity_id":e,"attributes":{}}]
    reg=[{"entity_id":v,"platform":"xiaomi_viomi","unique_id":"uid"},{"entity_id":e,"platform":"xiaomi_viomi","unique_id":"uid_battery_level"},{"entity_id":c,"platform":"robot_vacuum_map"}]
    robot,sensors,cam,attrs=identify(states,reg)
    assert (robot,cam,sensors["battery_level"])==(v,c,e)
    view=build_view(robot,sensors,cam,attrs,True)
    base={"views":[{"path":"pompa-ciepla","cards":[]}]}
    new=transform(base,view)
    assert new["views"][0]==base["views"][0] and len(base["views"])==1
    assert transform(new,view)==new
    assert "/media/viomi/pietro.png" in json.dumps(view)
    try: transform({"views":[{"path":VIEW}]},view)
    except RuntimeError: pass
    else: raise AssertionError("unrelated view replaced")
    print("SELFTEST OK")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true"); p.add_argument("--self-test",action="store_true")
    p.add_argument("--dashboard");p.add_argument("--vacuum");p.add_argument("--camera")
    args=p.parse_args()
    selftest()
    if args.self_test: return
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token: raise RuntimeError("Run in HA Terminal with Supervisor API permission")
    with urllib.request.urlopen(HELPER,timeout=25) as f: source=f.read(100000)
    scope={"__name__":"pinned_ws_helper"};exec(compile(source,HELPER,"exec"),scope)
    if os.environ.get("SUPERVISOR_TOKEN"):
        host,port,path="supervisor",80,"/core/websocket"
    else:
        host,port,path=os.environ.get("HA_WS_HOST","homeassistant"),int(os.environ.get("HA_WS_PORT","8123")),"/api/websocket"
    ws=scope["WS"](host,port,path)
    try:
        if ws.recv().get("type")!="auth_required": raise RuntimeError("Unexpected handshake")
        ws.send({"type":"auth","access_token":token})
        if ws.recv().get("type")!="auth_ok": raise RuntimeError("HA authentication refused")
        kwargs={"url_path":args.dashboard} if args.dashboard else {}
        original=ws.call("lovelace/config",force=True,**kwargs)
        robot,sensors,cam,attrs=identify(ws.call("get_states"),ws.call("config/entity_registry/list"),args.vacuum,args.camera)
        cfg=ws.call("get_config")
        media=Path("/media").is_dir() and "/media" in cfg.get("allowlist_external_dirs",[]) and "media_source" in cfg.get("components",[])
        view=build_view(robot,sensors,cam,attrs,media)
        out=transform(original,view)
        print("Vacuum:",robot,"sensors:",len(sensors),"map:",cam or "not configured","private media:",media)
        if not args.apply:
            print("DRY RUN - no changes");return
        if media:
            Path("/media/viomi").mkdir(exist_ok=True)
        if out==original:
            print("Already up to date");return
        if ws.call("lovelace/config",force=True,**kwargs)!=original: raise RuntimeError("Dashboard changed concurrently")
        print("Backup:",backup(original))
        ws.call("lovelace/config/save",config=out,**kwargs)
        if ws.call("lovelace/config",force=True,**kwargs)!=out: raise RuntimeError("Dashboard verification failed; see backup")
        print("SUCCESS: Odkurzacz view saved and verified. Other tabs unchanged.")
    finally: ws.close()
if __name__=="__main__": main()
