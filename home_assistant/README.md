# Home Assistant · HaierPi diagnostics 1.4.5_1

This directory contains **actual Lovelace YAML** aligned with the confirmed Home Assistant
entity IDs on the owner's system (25 November 2026) and with source release
[`petec999/hpi v1.4.5_1`](https://github.com/petec999/hpi/releases/tag/v1.4.5_1).

## Ready-to-use dashboard (recommended)

[`dashboards/haierpi-centrum-1.4.5_1.yaml`](dashboards/haierpi-centrum-1.4.5_1.yaml)
is a **whole-dashboard RAW configuration** with four tabs:

1. **Przegląd** — health, compressor Hz, hydraulic readings, overview of 14 diagnostics.
2. **Cykle i defrost** — all 8 RAM-only compressor/defrost counters and graphs.
3. **Obieg chłodniczy** — 6 derived circuit metrics plus actual HaierPi temperatures,
   bar pressures, Superheat, Subcooling and trends.
4. **Bilans energii** — existing Home Assistant energy-balance sensors and *daily*
   COP, not the unavailable `sensor.haier_cop_chwilowy`.

### Install via Home Assistant UI

1. In **Settings → Dashboards**, create a **new, user-editable** dashboard called
   `HaierPi · Diagnostyka`. Do not overwrite the existing dashboard.
2. Open the new dashboard, use **Edit dashboard** (pencil), then its **⋮** menu
   → **Raw configuration editor**.
3. Copy and paste the **entire** contents of
   `haierpi-centrum-1.4.5_1.yaml`, beginning with `title:` and `views:`.
4. Save. No Home Assistant restart, HACS/custom cards, sensor YAML or NanoPi
   installation is needed. Home Assistant's Recorder is responsible for charts.

### Add only one view to an existing dashboard

Use [`dashboards/haier-diagnostyka-view.yaml`](dashboards/haier-diagnostyka-view.yaml)
**in the YAML editor for a single view** (not in the whole-dashboard RAW editor).
It intentionally has no outer `views:` key. Back up the view first.
The single view is comprehensive and therefore longer than the four-tab dashboard.

## Entity/logic compatibility

The actual system contains all **8 `sensor.haierpi_diagnostics_*`** metrics and all
**6 `sensor.haierpi_advanced_diagnostics_*`** metrics. The compatibility
`unique_id` prefixes `HaierPi_PR6_` and `HaierPi_PR7_` originate in the
MQTT publisher, not in the display names or service unit names. Do not rename
these IDs casually or duplicate MQTT Discovery entities.

The live services on NanoPi are `haierpi-cycles` and `haierpi-circuit` and
record **no history on SD**. Daily counts reset at service/device restart.
The cards use **only actual listed HA IDs**; in particular the old
`sensor.haier_cop_chwilowy` is unavailable and does not appear as an entity
card. The overview and energy tab use the independently computed
`sensor.haier_bilans_cop_dobowy`, correctly labeled **daily COP**.

Some legacy source entities (e.g. `sensor.haierpi_pd`,
`sensor.haierpi_pch`, `sensor.haierpi_delta_temp_eco`) are unavailable:
the dashboard intentionally omits them. The native HaierPi MQTT sensors are
used instead of similarly named older `sensor.haier_*` sources when reading
the refrigeration circuit, because the two sets can disagree.

The presence of HA entities is **not** evidence that the currently deployed
*main controller* has already been upgraded to upstream Stable. The
`1.4.5_1` label here means compatibility with the separately distributed
diagnostic package; original core must be checked independently.

## Safety / interpretation

- All Lovelace cards are **read-only**.
- No MQTT control commands or automations are part of this dashboard.
- A sensor showing `0` is **not** treated as unavailable.
- `Defrost Chance` and `Szron` are separate user Home Assistant heuristics,
  not confirmation that the compressor is actively defrosting.
- `haier_bilans_cop_dobowy` is NOT instantaneous COP and is not provided by
  the read-only circuit bridge.
- Values updated at different times can disagree (e.g. native Twi/Two versus
  MQTT-derived water ΔT). Check entity timestamps/availability before making
  physical-system conclusions.
- No database on NanoPi: Home Assistant's Recorder owns all dashboard history.

GitHub Actions checks YAML and compares the 14 entity IDs with the pinned
`petec999/hpi` release source on relevant changes.
