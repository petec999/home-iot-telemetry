#!/usr/bin/env bash
# Install a SEPARATE, read-only HaierPi Lovelace YAML dashboard on Home Assistant OS.
# Does not alter existing dashboards, MQTT, automations, or NanoPi.
set -Eeuo pipefail
umask 077

ROOT="${HA_CONFIG_DIR:-/config}"
CFG="$ROOT/configuration.yaml"
DASH="$ROOT/dashboards/haierpi-centrum-1.4.5_1.yaml"
URL="https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/dashboards/haierpi-centrum-1.4.5_1.yaml"

echo "== HaierPi 1.4.5_1: read-only dashboard =="
test -f "$CFG" || { echo "ERROR: brak $CFG. Uruchom w terminalu HA, nie na NanoPi." >&2; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: brak python3" >&2; exit 1; }
command -v curl >/dev/null || { echo "ERROR: brak curl" >&2; exit 1; }
mkdir -p "$ROOT/dashboards"
TMP="$(mktemp "$ROOT/dashboards/.haierpi.XXXXXXXX")"
trap 'rm -f "$TMP"' EXIT
curl -fsSL --retry 2 --connect-timeout 10 --max-time 60 "$URL" -o "$TMP"
python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text(encoding="utf-8")
for item in ("title: HaierPi", "views:", "sensor.haierpi_diagnostics_compressor_starts_today",
             "sensor.haierpi_advanced_diagnostics_co_water_delta_t"):
    if item not in text:
        raise SystemExit("Downloaded dashboard failed content check: "+item)
print("YAML dashboard downloaded:",len(text),"bytes")
PY

# Inspect and precompute configuration BEFORE writing the fetched dashboard.
# Bail out on complex !include or conflicting Lovelace layouts instead of guessing.
python3 - "$CFG" <<'PY'
from pathlib import Path
import re,sys
s=Path(sys.argv[1]).read_text(encoding="utf-8")
lines=s.splitlines(keepends=True)
idx=[i for i,l in enumerate(lines) if re.match(r'^lovelace\s*:',l)]
if len(idx)>1:
    raise SystemExit("ERROR: duplicate top-level lovelace sections; no changes")
if len(idx)==1:
    line=lines[idx[0]]
    if not re.match(r'^lovelace:\s*(?:#.*)?$',line.strip()):
        raise SystemExit("ERROR: lovelace uses external include/inline value; manual setup required")
    end=next((i for i in range(idx[0]+1,len(lines))
              if re.match(r'^[A-Za-z_][\w-]*\s*:',lines[i])),len(lines))
    part=lines[idx[0]+1:end]
    dashboards=[x for x in part if re.match(r'^  dashboards\s*:',x)]
    if len(dashboards)>1 or (dashboards and not re.match(r'^  dashboards:\s*(?:#.*)?$',dashboards[0].rstrip())):
        raise SystemExit("ERROR: dashboards structure unsupported")
    if re.search(r'^    haierpi-diagnostyka\s*:', ''.join(part),flags=re.M):
        print("Dashboard already registered; config.yaml unchanged")
    else:
        print("Existing Lovelace section: new separate dashboard can be inserted")
else:
    print("No existing Lovelace section: new dashboard can be added safely")
PY

STAMP="$(date +%Y%m%d-%H%M%S)"
if [ -f "$DASH" ]; then
  if cmp -s "$TMP" "$DASH"; then
    echo "Dashboard YAML already current"
  else
    cp -p "$DASH" "$DASH.bak-$STAMP"
    cp "$TMP" "$DASH"
    chmod 644 "$DASH"
    echo "Updated dashboard; backup: $DASH.bak-$STAMP"
  fi
else
  install -m 644 "$TMP" "$DASH"
  echo "Installed dashboard: $DASH"
fi

python3 - "$CFG" "$STAMP" <<'PY'
from pathlib import Path
import os, re, stat, sys, tempfile

cfg=Path(sys.argv[1]); stamp=sys.argv[2]
s=cfg.read_text(encoding="utf-8")
lines=s.splitlines(keepends=True)
if lines and not lines[-1].endswith("\n"):
    lines[-1]+="\n"

key="haierpi-diagnostyka"
entry=(f"    {key}:\n"
       "      mode: yaml\n"
       "      filename: dashboards/haierpi-centrum-1.4.5_1.yaml\n"
       "      title: HaierPi Diagnostyka\n"
       "      icon: mdi:heat-pump\n"
       "      show_in_sidebar: true\n")
matches=[i for i,l in enumerate(lines) if re.match(r'^lovelace\s*:',l)]
if not matches:
    result="".join(lines).rstrip("\n")+"\n\nlovelace:\n  dashboards:\n"+entry
else:
    start=matches[0]
    end=next((i for i in range(start+1,len(lines))
              if re.match(r'^[A-Za-z_][\w-]*\s*:',lines[i])),len(lines))
    part=lines[start+1:end]
    if any(re.match(r'^    '+key+r'\s*:',x) for x in part):
        result="".join(lines)
    else:
        dash=[i for i,x in enumerate(part) if re.match(r'^  dashboards:\s*(?:#.*)?$',x.rstrip())]
        if dash:
            di=start+1+dash[0]
            de=next((i for i in range(di+1,end)
                     if re.match(r'^  [A-Za-z_][\w-]*\s*:',lines[i])),end)
            result="".join(lines[:de])+entry+"".join(lines[de:])
        else:
            result="".join(lines[:end])+"  dashboards:\n"+entry+"".join(lines[end:])
if result==s:
    print("Existing Lovelace dashboard entry unchanged")
else:
    backup=cfg.with_name(cfg.name+".bak-haierpi-"+stamp)
    backup.write_bytes(cfg.read_bytes())
    os.chmod(backup,stat.S_IMODE(cfg.stat().st_mode))
    fd,tmp=tempfile.mkstemp(prefix=".haierpi-config-",dir=cfg.parent)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        out.write(result)
    os.chmod(tmp,stat.S_IMODE(cfg.stat().st_mode))
    os.replace(tmp,cfg)
    print("Registration added. Backup:",backup)
print("PANEL URL: /haierpi-diagnostyka/haierpi-przeglad")
print("RESTART REQUIRED: HA Configuration -> Restart Home Assistant (or ha core restart)")
PY

# A config check is beneficial, but an unrelated HA check failure must not silently restart.
if command -v ha >/dev/null 2>&1; then
  echo "Checking Home Assistant config..."
  if ha core check; then
    echo "HA CONFIG OK. Restart Home Assistant once to register the new dashboard."
  else
    echo "WARNING: HA config check failed. Do not restart HA yet." >&2
    echo "Inspect the last configuration.yaml.bak-haierpi-* backup before proceeding." >&2
    exit 1
  fi
else
  echo "HA CLI unavailable. Check the configuration in Home Assistant before restarting."
fi
