# Home IoT Telemetry

Home Assistant dashboard integration and telemetry for Haier heat pumps, including compressor operation, defrost diagnostics, refrigerant circuit and energy balance.

## Current dashboard

The HaierPi 1.4.5_1 diagnostic migration integrates 14 diagnostic sensors into the existing **Pompa ciepła** tab, removes the obsolete instantaneous COP card and temporary diagnostic tabs, and displays room temperature, humidity and illuminance in **Klimatyzacja**. Existing unrelated dashboard views and automations are preserved.

### Install / update

From Home Assistant Terminal & SSH with Home Assistant API access:

```bash
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/merge-haierpi-panel.py | python3 -
```

The legacy `add-haierpi-views.py` entrypoint delegates to the same merger. The merger requires Python 3, network access, a UI-managed default Lovelace dashboard, and the expected existing heat pump and climate tabs. It uses Supervisor authentication or a locally supplied `HA_TOKEN`; never publish tokens. No HA restart is required.

The script backs up the complete dashboard under `/config/haierpi-lovelace-backups/` before saving, checks for concurrent edits and verifies the saved configuration. Restore the backup using the dashboard raw configuration editor (JSON is valid YAML), if needed. This changes dashboard presentation, not sensor definitions or equipment controls.

## Files

- [Dashboard migration](home_assistant/merge-haierpi-panel.py)
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
