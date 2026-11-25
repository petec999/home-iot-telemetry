# Home Assistant Configuration

This directory contains Home Assistant configuration files used by the **Home IoT Telemetry** project.

It will eventually include:

- Energy and temperature sensor definitions  
- MQTT integrations  
- Template sensors (e.g., domestic hot water and central heating energy calculations)  
- Automations  
- Dashboards  

At this stage, this directory serves as a structural placeholder for future configuration.


## HaierPi PR6/PR7 technical diagnostics view

`home_assistant/dashboards/haier-diagnostyka-view.yaml` is a **single Lovelace view** containing 8 confirmed PR6 counter entities, 6 confirmed PR7 circuit telemetry entities and Home Assistant recorder graphs.

Import only into a **new view** in the existing Home Assistant dashboard using the view's YAML editor, not into the whole dashboard YAML. No HaierPi update, service restart, or custom Lovelace cards required.

The separate `petec999/hpi` repository owns the HaierPi daemon, PR6/PR7 MQTT sidecars, and PR8 SQLite historian. PR8 does not expose native HA entities; the read-only reporting tool remains in `petec999/hpi/tools/pr8_report.py`. This HA repository owns only dashboard configuration and presentation.
