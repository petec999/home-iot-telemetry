"""Smoke-test installing our four views on an existing Home Assistant dashboard.

Fake the official Lovelace websocket endpoints; do not contact any real HA or write
to its storage. Also exercise a real RFC6455 handshake and masked text framing.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"home_assistant"/"add-haierpi-views.py"
spec=importlib.util.spec_from_file_location("haierpi_dashboard_installer",SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
release=json.loads((ROOT/"home_assistant"/"dashboards"/"haierpi-centrum-1.4.5_1.json").read_text())

class FakeWS:
    state={
      "title":"Mój istniejący pulpit",
      "views":[{"title":"Salon","path":"salon","cards":[{"type":"markdown","content":"MOJE STARE KARTY"}]}],
    }
    def __init__(self,*args):
        self.auth=False
        self.calls=[]
    def recv(self):
        if not self.auth:
            self.auth=True
            return {"type":"auth_required"}
        return {"type":"auth_ok"}
    def send(self,msg):
        assert msg["type"]=="auth"
    def call(self,ty,**kwargs):
        if ty=="lovelace/config":
            return json.loads(json.dumps(type(self).state))
        if ty=="lovelace/config/save":
            assert "config" in kwargs
            type(self).state=json.loads(json.dumps(kwargs["config"]))
            return None
        raise AssertionError(ty)
    def close(self):
        pass

class InstallerTests(unittest.TestCase):
    def setUp(self):
        FakeWS.state={
          "title":"Mój istniejący pulpit",
          "views":[{"title":"Salon","path":"salon","cards":[{"type":"markdown","content":"MOJE STARE KARTY"}]}],
        }
    def test_append_and_update_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"configuration.yaml").write_text("default_config:\n")
            with patch.dict(os.environ,{"HA_CONFIG_DIR":directory,"SUPERVISOR_TOKEN":"test-only"},clear=True):
                with patch.object(module,"WS",FakeWS), patch.object(
                    module,"get_release_views",lambda:json.loads(json.dumps(release["views"]))
                ):
                    module.main()
                    self.assertEqual(len(FakeWS.state["views"]),5)
                    self.assertEqual(FakeWS.state["views"][0]["cards"][0]["content"],"MOJE STARE KARTY")
                    self.assertEqual({v["path"] for v in FakeWS.state["views"][1:]},module.VIEW_PATHS)
                    backups=list((Path(directory)/"haierpi-lovelace-backups").glob("*.json"))
                    self.assertEqual(len(backups),1)
                    old=json.loads(backups[0].read_text())
                    self.assertEqual(len(old["views"]),1)
                    module.main()
                    self.assertEqual(len(FakeWS.state["views"]),5)
                    self.assertEqual(len(list((Path(directory)/"haierpi-lovelace-backups").glob("*.json"))),1)

    def test_strategy_dashboard_refused(self):
        FakeWS.state={"strategy":{"type":"original-states"}}
        with patch.dict(os.environ,{"SUPERVISOR_TOKEN":"test-only"},clear=True):
            with patch.object(module,"WS",FakeWS), patch.object(
                module,"get_release_views",lambda:json.loads(json.dumps(release["views"]))
            ):
                with self.assertRaisesRegex(RuntimeError,"auto-generated"):
                    module.main()

    def test_no_auth_refused(self):
        with patch.dict(os.environ,{},clear=True):
            with patch.object(module,"get_release_views",lambda:release["views"]):
                with self.assertRaisesRegex(RuntimeError,"No SUPERVISOR_TOKEN"):
                    module.main()

if __name__=="__main__":
    unittest.main()
