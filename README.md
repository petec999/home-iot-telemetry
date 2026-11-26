# Home IoT Telemetry

Home Assistant dashboard integration and telemetry for Haier heat pumps, including compressor operation, defrost diagnostics, refrigerant circuit and energy balance.

## Current dashboard — Stable diagnostics and Adaptive preview

The HaierPi 1.4.5_1 diagnostic migration integrates 14 diagnostic sensors into the existing **Pompa ciepła** tab, removes the obsolete instantaneous COP card and temporary diagnostic tabs, and displays room temperature, humidity and illuminance in **Klimatyzacja**. Existing unrelated dashboard views and automations are preserved.

The current [HaierPi 1.4.5_3 distribution](https://github.com/petec999/hpi/releases/tag/v1.4.5_3) also includes MQTT watchdog v2. The dashboard displays heartbeat freshness and last reception in the existing **Pompa ciepła** tab. Normal end-to-end reception was confirmed on the live NanoPi on 25 November 2026; actual outage recovery remains untested on hardware.

The read-only Heater A4A card (Adaptive preview) resolves the actual MQTT entity IDs and shows state, observed starts/runtime and a 48-hour history. Experimental heater control has been retired.

The Midea Cloud Control 0.2.1 panel retains supported Turbo and Sleep controls, temperatures and diagnostics; unsupported ECO and LED rows are removed for this installation.

### Install / update

From Home Assistant Terminal & SSH with Home Assistant API access:

```bash
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/merge-haierpi-panel.py | python3 -
```

For an already merged dashboard, add/update the MQTT status card and Midea panel separately (no new tabs or restart):

```bash
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/update-haier-watchdog-panel.py | python3 -
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/update-haier-heater-panel.py | python3 -
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/update-midea-panel.py | python3 -
```

The watchdog card requires `sensor.haierpi_mqtt_heartbeat`. It shows HA reception, not individual Modbus frame freshness. See [HA setup details](home_assistant/README.md).

The legacy `add-haierpi-views.py` was used for separate diagnostic tabs; do not run it after consolidation. It is also a pinned WebSocket helper for current installers. The merger requires Python 3, network access, a UI-managed default Lovelace dashboard, and the expected existing heat pump and climate tabs. It uses Supervisor authentication or a locally supplied `HA_TOKEN`; never publish tokens. No HA restart is required.

The script backs up the complete dashboard under `/config/haierpi-lovelace-backups/` before saving, checks for concurrent edits and verifies the saved configuration. Restore the backup using the dashboard raw configuration editor (JSON is valid YAML), if needed. This changes dashboard presentation, not sensor definitions or equipment controls.

## Files

- [Dashboard migration](home_assistant/merge-haierpi-panel.py)
- [MQTT status card updater](home_assistant/update-haier-watchdog-panel.py)
- [Read-only heater card updater](home_assistant/update-haier-heater-panel.py)
- [Midea climate panel updater](home_assistant/update-midea-panel.py)
- [Versioned dashboard source](home_assistant/dashboards/haierpi-centrum-1.4.5_1.json)
- [Regression tests](tests/test_merge_haierpi_panel.py)

Run tests locally from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

The tests use synthetic dashboards, not private household configuration.

## Related projects

- [HaierPi](https://github.com/petec999/hpi) — related heat pump software.
- [Midea Cloud Control](https://github.com/petec999/midea-cloud-control) — Home Assistant integration for cloud-controlled air conditioners.

## Scope and roadmap

The current focus is reliable telemetry and dashboard diagnostics. Further work may include historical energy analysis, Grafana visualization, and additional Modbus monitoring. These are not guaranteed to be implemented in this repository.

Do not commit Home Assistant tokens, credentials, private dashboard exports or household telemetry. Follow upstream licensing for any third-party code.
