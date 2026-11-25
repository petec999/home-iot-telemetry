#!/usr/bin/env python3
"""Compatibility entrypoint. Use merge-haierpi-panel.py for new installations."""
import urllib.request
URL = "https://raw.githubusercontent.com/petec999/home-iot-telemetry/main/home_assistant/merge-haierpi-panel.py"
if __name__ == "__main__":
    with urllib.request.urlopen(URL, timeout=25) as response:
        source = response.read()
    exec(compile(source, URL, "exec"), {"__name__": "__main__"})
