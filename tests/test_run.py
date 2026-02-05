from __future__ import annotations

import re
import unittest

from orchestrator.run import make_run_id


class RunTests(unittest.TestCase):
    def test_make_run_id_format(self) -> None:
        run_id = make_run_id()
        self.assertRegex(run_id, r"^run-\d{14}$")


if __name__ == "__main__":
    unittest.main()
