"""Regression tests for merging real HaierPi diagnostics into existing tabs.

Uses a deliberately small synthetic dashboard: never commit private HA config.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/"home_assistant"/"merge-haierpi-panel.py"
spec=importlib.util.spec_from_file_location("haierpi_merge",MOD)
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
release=json.loads((ROOT/"home_assistant"/"dashboards"/"haierpi-centrum-1.4.5_1.json").read_text(encoding="utf8"))

def make_dashboard():
    return {"title":"Dom","views":[
      {"path":"default_view","title":"Fotowoltaika","cards":[{"type":"entities","entities":["sensor.pv"]}]},
      {"path":"pompa-ciepla","title":"Pompa ciepła","cards":[
          {"type":"vertical-stack","cards":[
            {"type":"entities","title":"Pompa i CO",
             "entities":[{"entity":"sensor.haierpi_twi"},
                         {"entity":"sensor.haierpi_two"},
                         {"entity":"sensor.temperature_and_humidity_sensor_5_temperatura"}]},
            {"type":"entities","title":"Sterowanie",
             "entities":[{"entity":"select.haierpi_mode"}]}
          ]},
          {"type":"vertical-stack","cards":[
              {"type":"entities","title":"Energia",
               "entities":[{"entity":"sensor.haier_bilans_cop_dobowy"},
                           {"entity":"sensor.haierpi_twi"}]}
          ]},
          {"type":"vertical-stack","cards":[
              {"type":"gauge","entity":"sensor.haier_cop_chwilowy"},
              {"type":"history-graph","title":"COP old", "entities":[
                  {"entity":"sensor.haier_cop_chwilowy"}]},
              {"type":"history-graph","title":"COP mixed", "entities":[
                  {"entity":"sensor.haier_cop_chwilowy"},
                  {"entity":"sensor.haierpi_tao"}]},
              {"type":"gauge","entity":"sensor.haierpi_superheat"},
              {"type":"entities","title":"Raw", "entities":[
                  {"entity":"sensor.haierpi_twi"}, {"entity":"sensor.haierpi_psact"}]}
          ]},
          {"type":"entities","title":"temperatura dom","entities":[
              {"entity":"sensor.temperature_and_humidity_sensor_5_temperatura"},
              {"entity":"sensor.temperature_and_humidity_sensor_5_wilgotnosc"},
              {"entity":"sensor.temperature_and_humidity_sensor_5_natezenie_oswietlenia"}]},
          {"type":"entities","title":"Moj przelacznik",
           "entities":[{"entity":"switch.zasilanie_piec_gaz_socket_1"}]}
      ]},
      {"path":"klimatyzacja","title":"Klimatyzacja","type":"sections","sections":[
         {"type":"grid","cards":[
            {"type":"thermostat","entity":"climate.sypialnia_jasminowa"},
            {"type":"history-graph","title":"Klimatyzacja – temperatura pomieszczenia (48 h)",
             "entities":[{"entity":"climate.sypialnia_jasminowa"}]}
          ]}
      ]},
      {"path":"cwu","title":"CWU","cards":[{"type":"entities","entities":[
         {"entity":"switch.thr316d_ds18b20_on_off_switch"}]}]},
      *[{"path":path,"title":path,"cards":[{"type":"markdown","content":"extra view"}]}
        for path in sorted(app.EXTRA_PATHS)],
    ]}

class MergeTests(unittest.TestCase):
    def test_merge_preserves_all_original_nonhaier_views_and_controls(self):
        original=make_dashboard()
        result=app.transform(original,release["views"])
        paths=[v["path"] for v in result["views"]]
        self.assertEqual(paths,["default_view","pompa-ciepla","klimatyzacja","cwu"])
        self.assertEqual(result["views"][0],original["views"][0])
        self.assertEqual(result["views"][3],original["views"][3])
        pump=result["views"][1]
        dump=json.dumps(pump,ensure_ascii=False)
        self.assertNotIn("sensor.haier_cop_chwilowy",dump)
        self.assertIn("sensor.haier_bilans_cop_dobowy",dump)
        self.assertIn("switch.zasilanie_piec_gaz_socket_1",dump)
        self.assertEqual(len([x for x in pump["cards"] if x.get("title")=="Diagnostyka obiegu · 6 nowych wskaźników"]),1)
        self.assertIn("sensor.haierpi_diagnostics_defrost_starts_today",dump)
        self.assertIn("sensor.haierpi_advanced_diagnostics_pressure_delta",dump.replace("sensor.haierpi_advanced_diagnostics_refrigerant_pressure_delta","sensor.haierpi_advanced_diagnostics_pressure_delta"))
        self.assertEqual(len([x for x in pump["cards"] if x.get("title")=="temperatura dom"]),0)
        self.assertEqual(
          sum(1 for x in pump["cards"] if "sensor.haierpi_twi" in json.dumps(x)),
          1, "The repeated Twi in old entities should be cleaned, graphs excluded in synthetic fixture.")
        climate=result["views"][2]["sections"][0]["cards"]
        cond=[x for x in climate if x.get("title")=="Warunki w domu · Zigbee"]
        self.assertEqual(len(cond),1)
        self.assertIn("sensor.temperature_and_humidity_sensor_5_temperatura",json.dumps(cond[0]))
        graph=next(x for x in climate if x.get("type")=="history-graph")
        self.assertEqual(sum(app.entity_in(e)==app.ROOM for e in graph["entities"]),1)
        self.assertEqual(len(original["views"]),8,"Transformer must not mutate input")

    def test_idempotent(self):
        v=release["views"]
        result=app.transform(make_dashboard(),v)
        next_result=app.transform(result,v)
        self.assertEqual(result,next_result)

    def test_missing_pump_or_climate_is_safe(self):
        base=make_dashboard()
        base["views"]=[v for v in base["views"] if v.get("path")!="klimatyzacja"]
        with self.assertRaisesRegex(RuntimeError,"Expected original"):
            app.transform(base,release["views"])

if __name__=="__main__":
    unittest.main()
