from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_batch_assets.py"


def load_build_batch_assets_module():
    spec = importlib.util.spec_from_file_location("build_batch_assets", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BuildBatchAssetsTests(unittest.TestCase):
    def test_build_svg_overlays_raw_validation_scatter(self) -> None:
        module = load_build_batch_assets_module()

        series = [
            {
                "agent": "01 Ratchet",
                "best_validation": 0.45,
                "hidden_test": None,
                "best_so_far": [0.40, 0.45],
                "run_validation": [0.40, 0.42],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "chart.svg"
            module._build_svg(series, out_path, "Toy Chart", (1, 2))
            svg = out_path.read_text(encoding="utf-8")

        self.assertIn('class="best-line"', svg)
        self.assertIn('class="raw-point"', svg)


if __name__ == "__main__":
    unittest.main()
