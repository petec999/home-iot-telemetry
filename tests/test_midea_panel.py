"""Offline dashboard merge regression tests with synthetic registry IDs."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "midea_panel", Path(__file__).resolve().parents[1] / "home_assistant/update-midea-panel.py")
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


class DashboardTests(unittest.TestCase):
    def fixture(self):
        climate = "climate.example_renamed"
        registry = [{"entity_id": climate, "platform": "midea_cloud_control",
                     "unique_id": "123", "device_id": "own", "disabled_by": None}]
        for field, (domain, _, _) in panel.FIELDS.items():
            registry.append({"entity_id": f"{domain}.custom_{field}", "platform": "midea_cloud_control",
                             "unique_id": "123_" + field, "device_id": "own",
                             "disabled_by": "integration" if field == "eco" else None})
            registry.append({"entity_id": f"{domain}.foreign_{field}", "platform": "midea_cloud_control",
                             "unique_id": "999_" + field, "device_id": "other", "disabled_by": None})
        states = [{"entity_id": r["entity_id"]} for r in registry if not r["disabled_by"]]
        states += [{"entity_id": e} for e in panel.ROOM_ROWS]
        original = {"views": [
            {"path": "pompa-ciepla", "cards": [{"type": "tile", "entity": "sensor.pump"}]},
            {"path": "klimatyzacja", "sections": [{"type": "grid", "cards": [
                {"type": "thermostat", "entity": climate},
                {"type": "entities", "title": "Warunki w domu", "entities": [panel.ROOM]},
                {"type": "entities", "entities": ["switch.custom_turbo", "switch.other"]},
                {"type": "markdown", "content": "keep"},
                {"type": "history-graph", "title": "Custom history", "entities": [climate]},
            ]}]},
        ]}
        return original, registry, states

    def test_only_existing_view_and_device(self):
        config, registry, states = self.fixture()
        result = panel.transform(config, registry, states)
        self.assertEqual(result["views"][0], config["views"][0])
        cards = result["views"][1]["sections"][0]["cards"]
        refs = panel.refs(result["views"][1])
        self.assertIn("sensor.custom_indoor_temperature", refs)
        self.assertIn("switch.custom_turbo", refs)
        self.assertNotIn("switch.custom_eco", refs)
        self.assertFalse(any(".foreign_" in x for x in refs))
        self.assertIn("switch.other", refs)
        self.assertIn({"type": "markdown", "content": "keep"}, cards)
        self.assertTrue(any(c.get("title") == "Custom history" for c in cards))
        self.assertEqual(sum("switch.custom_turbo" in panel.refs(c) for c in cards), 1)

    def test_idempotent(self):
        config, registry, states = self.fixture()
        first = panel.transform(config, registry, states)
        self.assertEqual(first, panel.transform(first, registry, states))

    def test_missing_sensor_refuses(self):
        config, registry, states = self.fixture()
        states = [s for s in states if s["entity_id"] != "sensor.custom_indoor_temperature"]
        with self.assertRaises(RuntimeError):
            panel.transform(config, registry, states)

    def test_missing_climate_refuses(self):
        config, registry, states = self.fixture()
        registry = [r for r in registry if not r["entity_id"].startswith("climate.")]
        with self.assertRaises(RuntimeError):
            panel.transform(config, registry, states)


if __name__ == "__main__":
    unittest.main()
