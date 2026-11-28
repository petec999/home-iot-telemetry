#!/usr/bin/env python3
"""Install interactive room map card into our existing dashboard, using HA API."""
import argparse,copy,json,os,urllib.request
from pathlib import Path
JS = "/* Viomi V8 room controls: active map only, no external scripts. */\nclass ViomiRoomMap extends HTMLElement {\n  setConfig(config) {\n    if (!config.entity || !config.map_entity) throw Error(\"Missing vacuum or map entity\");\n    this.cfg=config; this.selected=new Set(); this.signature=\"\"; this.loaded=false; this.url=\"\"; this.volumeBusy=false;\n    if (!this.shadowRoot) this.attachShadow({mode:\"open\"});\n    this.shadowRoot.innerHTML='<style>:host{display:block} .body{padding:16px} .map{position:relative;line-height:0} img{width:100%;height:auto;display:block;border-radius:10px} .markers{position:absolute;inset:0;pointer-events:none} button{font:inherit;border:1px solid var(--divider-color);border-radius:8px;padding:8px 12px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer} button[aria-pressed=true]{background:var(--primary-color);color:white} button:disabled{opacity:.5;cursor:default} .pin{position:absolute;transform:translate(-50%,-50%);pointer-events:auto;font-weight:bold;box-shadow:0 1px 5px #0006;min-width:30px;padding:6px;line-height:1.1} .rooms,.controls{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px} .msg{color:var(--secondary-text-color);font-size:13px;margin:10px 0} .start{background:var(--primary-color);color:white} .volume{margin-top:16px;border-top:1px solid var(--divider-color);padding-top:12px}.volume input{width:100%;accent-color:var(--primary-color)} h3{margin:0 0 12px;font-size:17px}</style><ha-card><div class=\"body\"><h3>Mapa interaktywna · aktywna kondygnacja</h3><div class=\"map\"><img alt=\"Aktywna mapa odkurzacza\"><div class=\"markers\"></div></div><div class=\"msg\" role=\"status\"></div><div class=\"rooms\"></div><div class=\"controls\"><button class=\"start\">Sprzątaj wybrane pokoje</button><button class=\"clear\">Wyczyść wybór</button></div><div class=\"msg\">Znaczniki wskazują przybliżone środki pokoi. Zapisane obrazy innych pięter są tylko podglądem.</div><div class=\"volume\"><strong>Głośność komunikatów</strong><div class=\"msg volumeRead\"></div><label>Nowy poziom: <output>5</output>/10<input aria-label=\"Głośność komunikatów\" type=\"range\" min=\"0\" max=\"10\" step=\"1\" value=\"5\"></label><div class=\"controls\"><button class=\"volumeApply\">Ustaw głośność</button><button class=\"volumeMute\">Wycisz</button></div><div class=\"msg volumeMsg\" role=\"status\">0 = wyciszenie. Wybierz poziom i zatwierdź.</div></div></div></ha-card>';\n    this.img=this.shadowRoot.querySelector(\"img\");\n    this.markers=this.shadowRoot.querySelector(\".markers\");\n    this.roomsEl=this.shadowRoot.querySelector(\".rooms\");\n    this.msg=this.shadowRoot.querySelector(\".msg\");\n    this.start=this.shadowRoot.querySelector(\".start\");\n    this.img.onload=()=>{this.loaded=true;this.renderRooms();};\n    this.img.onerror=()=>{this.loaded=false;this.renderRooms();};\n    this.start.onclick=()=>this.run();\n    this.volume=this.shadowRoot.querySelector(\".volume input\");\n    this.volumeOut=this.shadowRoot.querySelector(\".volume output\");\n    this.volumeApply=this.shadowRoot.querySelector(\".volumeApply\");\n    this.volumeMute=this.shadowRoot.querySelector(\".volumeMute\");\n    this.volumeRead=this.shadowRoot.querySelector(\".volumeRead\");\n    this.volumeMsg=this.shadowRoot.querySelector(\".volumeMsg\");\n    this.volume.oninput=()=>{this.volumeOut.textContent=this.volume.value;};\n    this.volumeApply.onclick=()=>this.setVolume(Number(this.volume.value));\n    this.volumeMute.onclick=()=>{this.volume.value=\"0\";this.volumeOut.textContent=\"0\";this.setVolume(0);};\n    this.shadowRoot.querySelector(\".clear\").onclick=()=>{this.selected.clear();this.renderRooms();};\n  }\n  set hass(hass) {\n    this._hass=hass;\n    if(!this.cfg || !this.img)return;\n    const map=hass.states[this.cfg.map_entity], vac=hass.states[this.cfg.entity];\n    this.vac=vac; this.map=map;\n    if(this.volumeRead){\n      const raw=vac?.attributes?.voice_volume;\n      this.volumeRead.textContent=raw==null?\"Brak odczytu głośności\":\"Odczyt urządzenia (v_state): \"+raw;\n      const disabled=!vac||[\"unknown\",\"unavailable\"].includes(vac.state)||this.volumeBusy;\n      this.volumeApply.disabled=disabled;this.volumeMute.disabled=disabled;\n    }\n    const a=map?.attributes||{}, raw=a.rooms;\n    this.rooms=Object.entries(raw&&typeof raw===\"object\"?raw:{}).flatMap(([k,r])=>{\n      if(!r||typeof r!==\"object\")return [];\n      const id=Number(k), number=Number(r.number??k);\n      return Number.isInteger(id)&&id===number&&id>0&&id<=255?[{id,name:typeof r.name===\"string\"&&r.name.trim()?r.name:\"Pokój \"+id,r}]:[];\n    });\n    this.cal=a.calibration_points;\n    this.mapId=String(vac?.attributes?.map_id??\"\");\n    const sig=JSON.stringify([this.mapId,this.rooms,this.cal]);\n    if(sig!==this.signature){this.selected.clear();this.signature=sig;}\n    const picture=a.entity_picture;\n    const valid=typeof picture===\"string\"&&picture.startsWith(\"/\")&&!picture.startsWith(\"//\")&&map&&![\"unknown\",\"unavailable\"].includes(map.state);\n    const url=valid?picture+(picture.includes(\"?\")?\"&\":\"?\")+\"v=\"+encodeURIComponent(map.state):\"\";\n    if(url!==this.url){\n      this.url=url;this.loaded=false;\n      if(url){this.img.src=url;this.img.hidden=false;}else{this.img.removeAttribute(\"src\");this.img.hidden=true;}\n    }\n    this.renderRooms();\n  }\n  project(x,y){\n    const c=this.cal;\n    if(!Array.isArray(c)||c.length<3||![x,y].every(Number.isFinite))return null;\n    const [p,q,r]=c;\n    if(![p,q,r].every(t=>t?.vacuum&&t?.map&&[t.vacuum.x,t.vacuum.y,t.map.x,t.map.y].every(Number.isFinite)))return null;\n    const ax=q.vacuum.x-p.vacuum.x,ay=q.vacuum.y-p.vacuum.y,bx=r.vacuum.x-p.vacuum.x,by=r.vacuum.y-p.vacuum.y,det=ax*by-ay*bx;\n    if(!Number.isFinite(det)||Math.abs(det)<1e-10)return null;\n    const dx=x-p.vacuum.x,dy=y-p.vacuum.y,u=(dx*by-dy*bx)/det,v=(ax*dy-ay*dx)/det;\n    return [p.map.x+u*(q.map.x-p.map.x)+v*(r.map.x-p.map.x),p.map.y+u*(q.map.y-p.map.y)+v*(r.map.y-p.map.y)];\n  }\n  renderRooms(){\n    if(!this.roomsEl)return;\n    this.markers.replaceChildren();this.roomsEl.replaceChildren();\n    const available=this.loaded&&!!this.url&&this.rooms?.length>0;\n    const mapOk=/^[1-9]\\d*$/.test(this.mapId||\"\");\n    const idle=[\"docked\",\"idle\"].includes(this.vac?.state);\n    const supported=Boolean((this.vac?.attributes?.supported_features||0)&256);\n    for(const room of this.rooms||[]){\n      const pressed=this.selected.has(room.id);\n      const make=(label,pin=false)=>{\n        const b=document.createElement(\"button\");b.type=\"button\";b.textContent=label;b.title=room.name;b.setAttribute(\"aria-pressed\",String(pressed));b.disabled=!available||this.busy;\n        b.onclick=()=>{if(this.selected.has(room.id))this.selected.delete(room.id);else this.selected.add(room.id);this.renderRooms();};\n        if(pin)b.className=\"pin\";return b;\n      };\n      this.roomsEl.append(make(room.name));\n      const r=room.r, x=Number.isFinite(r.pos_x)?r.pos_x:(Number.isFinite(r.x0)&&Number.isFinite(r.x1)?(r.x0+r.x1)/2:NaN),y=Number.isFinite(r.pos_y)?r.pos_y:(Number.isFinite(r.y0)&&Number.isFinite(r.y1)?(r.y0+r.y1)/2:NaN);\n      const pt=this.project(x,y),w=this.img.naturalWidth,h=this.img.naturalHeight;\n      if(available&&pt&&w&&h&&pt[0]>=0&&pt[0]<=w&&pt[1]>=0&&pt[1]<=h){\n        const b=make(String(room.id),true);b.style.left=(100*pt[0]/w)+\"%\";b.style.top=(100*pt[1]/h)+\"%\";this.markers.append(b);\n      }\n    }\n    this.start.disabled=!(available&&mapOk&&idle&&supported&&this.selected.size&&!this.busy);\n    this.msg.textContent=this.error||(!this.loaded?\"Oczekiwanie na obraz mapy.\":!this.rooms?.length?\"Mapa nie zawiera identyfikatorów pomieszczeń. Podziel mapę w Xiaomi Home.\":!mapOk?\"Brak aktualnego ID mapy lokalnej.\":!idle?\"Zatrzymaj robota lub poczekaj na powrót do bazy.\":\"Mapa \"+this.mapId+\" · wybrane pokoje: \"+this.selected.size);\n  }\n  async run(){\n    if(this.start.disabled)return;\n    const ids=[...this.selected], names=this.rooms.filter(r=>ids.includes(r.id)).map(r=>r.name);\n    if(!window.confirm(\"Czy aktywna mapa odpowiada kondygnacji, na której jest robot? Sprzątać: \"+names.join(\", \")+\"?\"))return;\n    this.busy=true;this.error=\"\";this.renderRooms();\n    try{\n      await this._hass.callService(\"vacuum\",\"send_command\",{entity_id:this.cfg.entity,command:\"viomi_clean_rooms\",params:[this.mapId,...ids]});\n      this.selected.clear();this.error=\"Polecenie wysłane. Sprawdź stan robota.\";\n    }catch(e){this.error=\"Polecenie odrzucone: \"+(e?.message||\"sprawdź log HA\");}\n    finally{this.busy=false;this.renderRooms();}\n  }\n  async setVolume(level){\n    if(this.volumeBusy||!Number.isInteger(level)||level<0||level>10||!this.vac||[\"unknown\",\"unavailable\"].includes(this.vac.state))return;\n    this.volumeBusy=true;this.volumeApply.disabled=true;this.volumeMute.disabled=true;\n    try{\n      await this._hass.callService(\"vacuum\",\"send_command\",{entity_id:this.cfg.entity,command:\"set_voice\",params:[level===0?0:1,level]});\n      this.volumeMsg.textContent=\"Polecenie wysłane: \"+level+\"/10. Odczyt urządzenia aktualizuje się okresowo.\";\n    }catch(e){this.volumeMsg.textContent=\"Błąd ustawienia głośności: \"+(e?.message||\"sprawdź log HA\");}\n    finally{this.volumeBusy=false;this.volumeApply.disabled=false;this.volumeMute.disabled=false;}\n  }\n  getCardSize(){return 7;}\n}\nif(!customElements.get(\"viomi-room-map\"))customElements.define(\"viomi-room-map\",ViomiRoomMap);\n"
URL="/local/viomi/viomi-room-map.js?v=2"
TYPE="custom:viomi-room-map"
BASE="https://raw.githubusercontent.com/petec999/home-iot-telemetry/b53e00ac956905e22e8db62af24a071f290a6f73/home_assistant/viomi/install-dashboard.py"
def load(url):
    with urllib.request.urlopen(url,timeout=25) as f: source=f.read(200000)
    scope={"__name__":"helper"}
    exec(compile(source,url,"exec"),scope)
    return scope
def transform(original,vac,cam):
    out=copy.deepcopy(original)
    views=[v for v in out["views"] if v.get("path")=="odkurzacz"]
    if len(views)!=1 or "VIOMI_DASHBOARD_V1" not in json.dumps(views[0]):
        raise RuntimeError("Run our dashboard installer first")
    view=views[0]
    card={"type":TYPE,"entity":vac,"map_entity":cam}
    # Replace only the interactive card or existing active image, retain snapshots and all other tabs.
    def walk(cards):
        for i,c in enumerate(cards):
            if c.get("type")==TYPE or (c.get("type")=="picture-entity" and c.get("name")=="Mapa aktywna"):
                cards[i]=card
                return True
            if isinstance(c.get("cards"),list) and walk(c["cards"]): return True
        return False
    if not walk(view["cards"]): view["cards"].insert(2,card)
    return out
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard");p.add_argument("--camera");p.add_argument("--vacuum")
    p.add_argument("--apply",action="store_true");p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    base={"views":[{"path":"odkurzacz","cards":[{"type":"markdown","content":"VIOMI_DASHBOARD_V1"},{"type":"vertical-stack","cards":[{"type":"picture-entity","name":"Mapa aktywna"},{"type":"picture","image":"floor.png"}]}]},{"path":"other","cards":[]}]}
    result=transform(base,"vacuum.test","image.test")
    assert result["views"][1]==base["views"][1] and transform(result,"vacuum.test","image.test")==result
    assert "floor.png" in json.dumps(result) and TYPE in json.dumps(result)
    print("Dashboard transformation self-test OK")
    if args.self_test:return
    token=os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
    if not token:raise RuntimeError("Run in Home Assistant Terminal")
    dash=load(BASE);helper=load(dash["HELPER"])
    if os.environ.get("SUPERVISOR_TOKEN"):host,port,path="supervisor",80,"/core/websocket"
    else:host,port,path=os.environ.get("HA_WS_HOST","homeassistant"),int(os.environ.get("HA_WS_PORT","8123")),"/api/websocket"
    ws=helper["WS"](host,port,path)
    try:
        if ws.recv().get("type")!="auth_required":raise RuntimeError("Unexpected handshake")
        ws.send({"type":"auth","access_token":token})
        if ws.recv().get("type")!="auth_ok":raise RuntimeError("Authentication failed")
        kw={"url_path":args.dashboard} if args.dashboard else {}
        original=ws.call("lovelace/config",force=True,**kw)
        states=ws.call("get_states")
        vac,sensors,cam,attrs=dash["identify"](states,ws.call("config/entity_registry/list"),args.vacuum,args.camera)
        if not cam:raise RuntimeError("No map entity found")
        manifest=json.loads(Path("/config/custom_components/xiaomi_viomi/manifest.json").read_text())
        if manifest.get("version")!="0.1.1":raise RuntimeError("Install Viomi 0.1.1 and restart Core first")
        state=next(x for x in states if x["entity_id"]==cam)
        rooms=state.get("attributes",{}).get("rooms") or {}
        print("Vacuum:",vac,"map:",cam,"room IDs:",list(rooms),"active map ID:",attrs.get("map_id"))
        new=transform(original,vac,cam)
        if not args.apply:print("Dry run only");return
        dest=Path("/config/www/viomi/viomi-room-map.js")
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_suffix(".tmp");tmp.write_text(JS);os.replace(tmp,dest)
        resources=ws.call("lovelace/resources")
        matching=[r for r in resources if r.get("url","").split("?")[0]==URL.split("?")[0]]
        if len(matching)>1:raise RuntimeError("Duplicate Viomi map resources")
        if not matching:ws.call("lovelace/resources/create",res_type="module",url=URL)
        elif matching[0].get("url")!=URL:ws.call("lovelace/resources/update",resource_id=matching[0]["id"],res_type="module",url=URL)
        if new!=original:
            if ws.call("lovelace/config",force=True,**kw)!=original:raise RuntimeError("Dashboard changed concurrently")
            print("Backup:",dash["backup"](original))
            ws.call("lovelace/config/save",config=new,**kw)
            if ws.call("lovelace/config",force=True,**kw)!=new:raise RuntimeError("Dashboard verification failed")
        print("SUCCESS: interactive map installed. Ctrl+F5.")
    finally:ws.close()
if __name__=="__main__":main()
