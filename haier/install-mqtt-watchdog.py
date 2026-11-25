#!/usr/bin/env python3
"""Install a read-only end-to-end MQTT watchdog into HaierPi's snapshot tick.

Run on HaierPi. No network access or service restart during installation.
"""
import argparse
import os
import shutil
import stat
import tempfile
from datetime import datetime
from pathlib import Path

MARK = "# HOME-IOT MQTT WATCHDOG v1"
WATCHDOG = r'''
# HOME-IOT MQTT WATCHDOG v1
import threading as _wd_threading
import time as _wd_time
import secrets as _wd_secrets
import json as _wd_json
import hashlib as _wd_hashlib

_wd_lock = _wd_threading.Lock()
_wd_since = None
_wd_last_ok = None
_wd_status = None
_wd_discovery_at = 0.0
_wd_scope = None
_wd_failures = 0
_wd_recoveries = 0

def _haierpi_watchdog_tick():
    """Run only after a scheduled MQTT snapshot; never block the scheduler."""
    if str(globals().get("use_mqtt", "0")) != "1":
        return
    if not _wd_lock.acquire(blocking=False):
        return
    try:
        _wd_threading.Thread(target=_haierpi_watchdog_worker,
                             name="ha-mqtt-watchdog", daemon=True).start()
    except Exception:
        _wd_lock.release()
        logging.exception("MQTT watchdog could not start")

def _haierpi_watchdog_worker():
    global _wd_since, _wd_last_ok, _wd_status, _wd_discovery_at, _wd_scope
    global _wd_failures, _wd_recoveries
    try:
        now = _wd_time.monotonic()
        topic = str(globals().get("mqtt_topic", "")).strip()
        prefix = str(globals().get("ha_mqtt_discovery_prefix", "")).strip("/")
        ha = config["HOMEASSISTANT"]
        address = ha.get("HAADDR", "").strip()
        port = ha.get("HAPORT", "").strip()
        token = ha.get("KEY", "").strip()
        base = address.rstrip("/") + (":" + port if port else "")
        scope = (topic, prefix, base)
        if _wd_scope != scope:
            _wd_scope = scope
            _wd_since = now
            _wd_last_ok = None
            _wd_status = None
            _wd_discovery_at = 0.0
        interval = max(2, int(globals().get("mqtt_snapshot_interval_s", 30) or 30))
        warn_after = max(90, 3 * interval)
        alarm_after = max(180, 6 * interval)
        cl = globals().get("client")
        reason = "unknown"
        if not address or not token or not topic or not prefix or str(globals().get("ha_mqtt_discovery", "0")) != "1":
            reason = "HA API or MQTT discovery not configured"
        elif cl is None or not cl.is_connected():
            reason = "broker disconnected"
            _wd_discovery_at = 0.0
        else:
            import requests
            ident = _wd_hashlib.sha256(topic.encode()).hexdigest()[:12]
            entity = "sensor.haierpi_mqtt_heartbeat"
            state_topic = topic + "/haierpi/watchdog_heartbeat"
            discovery = prefix + "/sensor/haierpi_watchdog_" + ident + "/config"
            nonce = str(_wd_time.time_ns()) + "-" + _wd_secrets.token_hex(6)
            if not _wd_discovery_at or now - _wd_discovery_at >= 300:
                cfg = {"name": "HaierPi MQTT heartbeat",
                       "unique_id": "haierpi_watchdog_" + ident,
                       "default_entity_id": entity,
                       "state_topic": state_topic,
                       "expire_after": max(120, 4 * interval),
                       "icon": "mdi:heart-pulse"}
                info = cl.publish(discovery, _wd_json.dumps(cfg), qos=1, retain=True)
                if info.rc == 0:
                    _wd_discovery_at = now
            info = cl.publish(state_topic, nonce, qos=1, retain=False)
            if info.rc != 0:
                reason = "MQTT publish rejected (rc=%s)" % info.rc
            else:
                headers = {"Authorization": "Bearer " + token,
                           "Accept": "application/json"}
                reason = "HA has not reported current heartbeat"
                for delay in (1, 2, 4):
                    _wd_time.sleep(delay)
                    if globals().get("client") is not cl or str(globals().get("use_mqtt", "0")) != "1":
                        return
                    try:
                        resp = requests.get(base + "/api/states/" + entity,
                                            headers=headers, timeout=(2, 3),
                                            allow_redirects=False)
                        if resp.status_code == 200:
                            if resp.json().get("state") == nonce:
                                reason = "ok"
                                break
                            reason = "HA has not reported current heartbeat"
                        else:
                            reason = "HA API HTTP %s" % resp.status_code
                            if resp.status_code in (401, 403):
                                break
                            if resp.status_code == 404:
                                # Discovery may be delayed or entity ID renamed.
                                _wd_discovery_at = 0.0
                    except Exception as exc:
                        reason = "HA API " + type(exc).__name__
        now = _wd_time.monotonic()
        if reason == "ok":
            previous = _wd_status
            _wd_last_ok = now
            _wd_status = "ok"
            if previous != "ok":
                if previous and previous.startswith(("warning:", "alarm:")):
                    _wd_recoveries += 1
                logging.info("MQTT watchdog OK: HA confirmed heartbeat (failures=%s recoveries=%s)",
                             _wd_failures, _wd_recoveries)
        else:
            age = now - (_wd_last_ok if _wd_last_ok is not None else _wd_since)
            level = "alarm" if age >= alarm_after else "warning" if age >= warn_after else "waiting"
            status = level + ": " + reason
            if status != _wd_status:
                if level == "warning" and not (_wd_status or "").startswith(("warning:", "alarm:")):
                    _wd_failures += 1
                elif level == "alarm" and not (_wd_status or "").startswith(("warning:", "alarm:")):
                    _wd_failures += 1
                log = logging.error if level == "alarm" else logging.warning if level == "warning" else logging.info
                log("MQTT watchdog %s; no verified reception for %.0fs", status, age)
                _wd_status = status
    except Exception as exc:
        # Never include credentials or raw HTTP content in diagnostic logs.
        logging.warning("MQTT watchdog internal error: %s", type(exc).__name__)
    finally:
        _wd_lock.release()

'''

def patch(source):
    if MARK in source:
        return source
    anchor = "def mqtt_snapshot_tick():\n"
    snapshot = "    _mqtt_snapshot_last_ts = now\n    mqtt_publish_snapshot()\n"
    import re
    handler_pattern = r"(?m)^def on_message\(client,[ \t]*userdata,[ \t]*msg\):[ \t]*(?:#[^\n]*)?\n"
    handlers = list(re.finditer(handler_pattern, source))
    if len(handlers) != 1:
        raise RuntimeError("Expected exactly one on_message(client, userdata, msg); nothing changed")
    for item in (anchor, snapshot):
        if source.count(item) != 1:
            raise RuntimeError("Unexpected HaierPi source layout; nothing changed: " + item.strip())
    # Keep the original signature and comment, including trailing whitespace.
    handler = handlers[0].group(0)
    source = source.replace(anchor, WATCHDOG + "\n" + anchor, 1)
    source = source.replace(snapshot, snapshot + "    _haierpi_watchdog_tick()\n", 1)
    source = source.replace(handler, handler +
        '    if msg.topic == str(mqtt_topic) + "/haierpi/watchdog_heartbeat":\n'
        '        return\n', 1)
    return source

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", default="/opt/haier/main.py")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    path = Path(args.path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Expected a regular HaierPi main.py")
    raw = path.read_bytes()
    source = raw.decode("utf-8")
    updated = patch(source)
    compile(updated, str(path), "exec")
    if updated == source:
        print("Watchdog already installed; no change.")
        return
    if args.dry_run:
        print("Compatible source; patched Python compiles. No changes.")
        return
    st = path.stat()
    backup = path.with_name(path.name + ".before-mqtt-watchdog-" +
                            datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    shutil.copy2(path, backup)
    fd, tmp = tempfile.mkstemp(prefix=".mqtt-watchdog-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(updated.encode("utf-8"))
            os.fchmod(f.fileno(), stat.S_IMODE(st.st_mode))
            if os.geteuid() == 0:
                os.fchown(f.fileno(), st.st_uid, st.st_gid)
            f.flush()
            os.fsync(f.fileno())
        if path.read_bytes() != raw:
            raise RuntimeError("Source changed during installation")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print("Installed MQTT watchdog. Backup:", backup)
    print("No restart performed. Activate at a suitable time with systemctl restart haier")

if __name__ == "__main__":
    main()
