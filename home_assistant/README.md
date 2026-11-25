# Home Assistant · HaierPi 1.4.5_1

The owner already has a working Home Assistant panel. **The recommended deployment
adds four new diagnostics tabs to the EXISTING/default dashboard**, without
creating a separate dashboard and without deleting any existing cards.

## One command in Home Assistant Terminal & SSH

```sh
curl -fsSL https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/add-haierpi-views.py | python3 -
```

Requirements: run this **on the Home Assistant machine in Terminal/SSH add-on**,
not on NanoPi `HaierPi`. The add-on should have the Home Assistant API permission
(`SUPERVISOR_TOKEN`). A direct connection using a private `HA_TOKEN` is supported
for advanced users who cannot expose the Supervisor proxy. Do **not** paste tokens
into chat, GitHub, or a dashboard.

The script uses the official `lovelace/config` and `lovelace/config/save`
WebSocket APIs rather than writing `.storage` or changing
`configuration.yaml`. It downloads JSON generated from our checked-in YAML
on GitHub, verifies the named tabs and key real HA entities, then:

1. Fetches the existing/default dashboard.
2. Appends/updates only the four namespaced HaierPi tabs:
   `haierpi-przeglad`, `haierpi-cykle`, `haierpi-obieg`, `haierpi-bilans`.
3. Saves a full backup of the **old dashboard** under
   `/config/haierpi-lovelace-backups/` before updating.
4. Saves via the HA WebSocket API, rereads and verifies the result.

Other views and their cards are preserved. Re-running is idempotent; no restart
of Home Assistant or NanoPi is needed. If the current dashboard is YAML-managed
or auto-generated, or permissions are insufficient, the script refuses to
change it and prints a reason. A verified backup can be restored using the same
official WebSocket API, not by editing `.storage` while HA runs.

## What the new tabs display

- **Przegląd:** status, compressor fact/fset, temperature, daily COP (if defined)
  and availability checks.
- **Cykle i defrost:** eight RAM-only MQTT counters from
  `haierpi-cycles.service`, defrost context and graphs.
- **Obieg chłodniczy:** six calculated read-only metrics from
  `haierpi-circuit.service`; live Twi/Two, Td, Ts, TsatPs/TSatPd, pressures
  and Superheat/Subcooling.
- **Bilans energii:** existing independent Home Assistant energy and COP
  templates. The unavailable instantaneous COP is intentionally omitted.

These entities were confirmed on the owner's actual HA installation on
25 November 2026. The 14 bridge entity IDs are additionally checked in CI
against `petec999/hpi` tag `v1.4.5_1`. Compatibility IDs in MQTT retain
their old prefixes to avoid duplicates; display names are descriptive.

The dashboard files remain available for manual import or YAML-managed HA:

- `dashboards/haierpi-centrum-1.4.5_1.yaml`: full independent
  four-tab dashboard template, **not the preferred terminal method**.
- `dashboards/haier-diagnostyka-view.yaml`: one view for manual insertion.
- `dashboards/haierpi-centrum-1.4.5_1.json`: generated JSON used
  automatically by the terminal installer.

The label 1.4.5_1 denotes the dashboard/add-on distribution, **not confirmation
that the original running NanoPi core has been upgraded to upstream Stable**.

All dashboard functionality is read-only and does not transmit control
commands, change existing heating automations, or store diagnostics on the
NanoPi SD card. Counters in NanoPi RAM reset on its reboot; Home Assistant
Recorder provides long-term history.
