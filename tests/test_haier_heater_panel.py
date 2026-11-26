import runpy
import unittest
from pathlib import Path
from copy import deepcopy
m=runpy.run_path(str(Path(__file__).resolve().parents[1]/"home_assistant/update-haier-heater-panel.py"))
class HeaterPanelTest(unittest.TestCase):
    def setUp(self):
        self.registry=[{"platform":"mqtt","unique_id":uid,"entity_id":domain+".renamed_"+str(i),"device_id":"haier"} for i,(uid,(domain,_,_)) in enumerate(m["FIELDS"].items())]
        self.states=[{"entity_id":r["entity_id"]} for r in self.registry]
        self.config={"views":[{"path":"pompa-ciepla","cards":[{"type":"markdown","title":"HaierPi · komunikacja MQTT"},{"type":"entities","title":"Existing","entities":["sensor.other"]}]},{"path":"cwu","cards":[]}]}
    def test_merge_and_idempotence(self):
        r=m["transform"](self.config,self.registry,self.states)
        self.assertEqual(r["views"][1],self.config["views"][1])
        self.assertEqual(r["views"][0]["cards"][1]["title"],m["TITLE"])
        self.assertEqual(len(r["views"][0]["cards"][1]["entities"]),3)
        self.assertEqual(r,m["transform"](r,self.registry,self.states))
        self.assertEqual(len(self.config["views"][0]["cards"]),2)
    def test_missing_entity_aborts(self):
        with self.assertRaises(RuntimeError):
            m["transform"](self.config,self.registry[:-1],self.states)
    def test_section_layout(self):
        c=deepcopy(self.config)
        v=c["views"][0]
        v["sections"]=[{"cards":v.pop("cards")}]
        r=m["transform"](c,self.registry,self.states)
        self.assertEqual(r["views"][0]["sections"][0]["cards"][1]["title"],m["TITLE"])

    def test_removes_old_controls(self):
        c=deepcopy(self.config)
        c["views"][0]["cards"].append({"type":"entities","title":m["TITLE"],"entities":["select.old_heater","sensor.old_reason"]})
        c["views"][0]["cards"].append({"type":"history-graph","title":m["HISTORY"],"entities":["select.old_heater"]})
        r=m["transform"](c,self.registry,self.states)
        self.assertNotIn("select.old_heater",str(r))
        self.assertNotIn("sensor.old_reason",str(r))
        self.assertEqual(len([card for card in r["views"][0]["cards"] if card.get("title")==m["TITLE"]]),1)
