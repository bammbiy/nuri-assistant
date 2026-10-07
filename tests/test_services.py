from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.nuri_assistant.companion import CompanionSettings
from src.nuri_assistant.services import Services


class ServicesTest(unittest.TestCase):
    def test_wiring_without_tk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CompanionSettings()
            services = Services(Path(tmp), lambda: settings)

            names = {spec["function"]["name"] for spec in services.toolbox.specs}
            self.assertTrue({"add_event", "add_todo", "add_price_watch", "start_focus_timer"} <= names)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["companion.sqlite3", "history.sqlite3"])

            # Price sources follow the settings as they change at runtime.
            self.assertEqual(services.price_sources(), [])
            settings = replace(settings, naver_client_id="id", naver_client_secret="secret")
            self.assertEqual(len(services.price_sources()), 1)


if __name__ == "__main__":
    unittest.main()
