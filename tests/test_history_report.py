from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from autoresearch.agent_report import parse_report_fields
from autoresearch.cli import main
from autoresearch.history_report import (
    build_comparison_report,
)


def make_history(rows: list[str]) -> str:
    lines = [
        "# History",
        "",
        "| run_id | benchmark | dataset | candidate | model | validation_score | rank | backend | artifact | run_best_candidate | run_best_validation | agent_best_candidate | agent_best_validation | dataset_model_best_agent | dataset_model_best_candidate | dataset_model_best_validation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(rows)
    lines.append("")
    return "\n".join(lines)


def make_report(entries: list[tuple[str, str]]) -> str:
    lines = ["# Report", ""]
    for run_id, report_text in entries:
        lines.append(f"## Run `{run_id}`")
        lines.append(report_text)
        lines.append("")
    return "\n".join(lines)


class HistoryReportTests(unittest.TestCase):
    def write_text(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def test_parse_report_fields_extracts_labeled_sections(self) -> None:
        fields = parse_report_fields(
            "Hypothesis: scaling helps. Decision: keep minmax. Verdict: pending."
        )

        self.assertEqual(fields["Hypothesis"], "scaling helps.")
        self.assertEqual(fields["Decision"], "keep minmax.")
        self.assertEqual(fields["Verdict"], "pending.")

    def test_parse_report_fields_extracts_advanced_doe_sections(self) -> None:
        fields = parse_report_fields(
            "Stage: screening. Anchor: mlp_anchor. Question: does width matter. "
            "Factors: hidden_dims. Levels: 64x32 vs 128x64. Alias risk: low. "
            "Prediction: wider should help. Observed signal: improvement on the treatment. "
            "Belief: hidden_dims looks active. Decision: keep wider anchor. Next: interaction check."
        )

        self.assertEqual(fields["Stage"], "screening.")
        self.assertEqual(fields["Anchor"], "mlp_anchor.")
        self.assertEqual(fields["Question"], "does width matter.")
        self.assertEqual(fields["Alias risk"], "low.")
        self.assertEqual(fields["Belief"], "hidden_dims looks active.")
        self.assertEqual(fields["Next"], "interaction check.")

    def test_build_comparison_report_aggregates_best_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_alpha = root / "agents" / "agent_alpha"
            agent_beta = root / "agents" / "agent_beta"
            run_a1 = "20260406T010000000000Z-agent_alpha-bench_a"
            run_a2 = "20260406T020000000000Z-agent_alpha-bench_a"
            run_b1 = "20260406T010500000000Z-agent_beta-bench_a"
            run_b2 = "20260406T020500000000Z-agent_beta-bench_a"
            self.write_text(
                root / ".work" / "agents" / "agent_alpha" / "history.md",
                make_history(
                    [
                        f"| {run_a1} | bench_a | toy | control_a | svm | 0.100000 | 1 | sklearn | `.work/runs/a1.json` | control_a | 0.100000 | control_a | 0.100000 | agent_alpha | control_a | 0.100000 |",
                        f"| {run_a2} | bench_a | toy | c_high | svm | 0.160000 | 1 | sklearn | `.work/runs/a2.json` | c_high | 0.160000 | c_high | 0.160000 | agent_alpha | c_high | 0.160000 |",
                        f"| {run_a2} | bench_a | toy | c_low | svm | 0.120000 | 2 | sklearn | `.work/runs/a2.json` | c_high | 0.160000 | c_high | 0.160000 | agent_alpha | c_high | 0.160000 |",
                    ]
                ),
            )
            self.write_text(
                root / ".work" / "agents" / "agent_alpha" / "report.md",
                make_report(
                    [
                        (run_a1, "Hypothesis: start raw. Decision: establish baseline. Verdict: pending."),
                        (run_a2, "Change: raise C only. Why: baseline weak. Interpretation: score improved."),
                    ]
                ),
            )
            self.write_text(
                root / ".work" / "agents" / "agent_beta" / "history.md",
                make_history(
                    [
                        f"| {run_b1} | bench_a | toy | control_b | svm | 0.110000 | 1 | sklearn | `.work/runs/b1.json` | control_b | 0.110000 | control_b | 0.110000 | agent_beta | control_b | 0.110000 |",
                        f"| {run_b2} | bench_a | toy | scaled_b | svm | 0.150000 | 1 | sklearn | `.work/runs/b2.json` | scaled_b | 0.150000 | scaled_b | 0.150000 | agent_beta | scaled_b | 0.150000 |",
                        f"| {run_b2} | bench_a | toy | clipped_b | svm | 0.130000 | 2 | sklearn | `.work/runs/b2.json` | scaled_b | 0.150000 | scaled_b | 0.150000 | agent_beta | scaled_b | 0.150000 |",
                    ]
                ),
            )
            self.write_text(
                root / ".work" / "agents" / "agent_beta" / "report.md",
                make_report(
                    [
                        (run_b1, "Hypothesis: test normalization first. Decision: compare preprocessing. Verdict: pending."),
                        (run_b2, "Hypothesis: scaling helps. Decision: keep normalization. Verdict: supported."),
                    ]
                ),
            )

            report = build_comparison_report(
                root=root,
                agent_dirs=[agent_alpha, agent_beta],
                benchmark_id="bench_a",
                model_family="svm",
                title="Toy Report",
            )

            self.assertEqual(report.title, "Toy Report")
            self.assertEqual(len(report.agents), 2)
            self.assertEqual(report.agents[0].rounds[0].best_candidate, "control_a")
            self.assertEqual(report.agents[0].rounds[1].best_candidate, "c_high")
            self.assertAlmostEqual(report.agents[0].rounds[1].best_validation_score, 0.16)
            self.assertEqual(report.agents[0].rounds[1].report_fields["Interpretation"], "score improved.")
            self.assertEqual(report.agents[1].rounds[1].report_fields["Decision"], "keep normalization.")

    def test_build_comparison_report_reads_runtime_history_from_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "agent_alpha"
            agent_dir.mkdir(parents=True, exist_ok=True)
            run_a1 = "20260406T010000000000Z-agent_alpha-bench_a"
            run_a2 = "20260406T020000000000Z-agent_alpha-bench_a"
            self.write_text(
                root / ".work" / "agents" / "agent_alpha" / "history.md",
                make_history(
                    [
                        f"| {run_a1} | bench_a | toy | control_a | svm | 0.100000 | 1 | sklearn | `.work/runs/a1.json` | control_a | 0.100000 | control_a | 0.100000 | agent_alpha | control_a | 0.100000 |",
                        f"| {run_a2} | bench_a | toy | c_high | svm | 0.160000 | 1 | sklearn | `.work/runs/a2.json` | c_high | 0.160000 | c_high | 0.160000 | agent_alpha | c_high | 0.160000 |",
                    ]
                ),
            )
            self.write_text(
                root / ".work" / "agents" / "agent_alpha" / "report.md",
                make_report(
                    [
                        (run_a1, "Hypothesis: start raw. Decision: establish baseline."),
                        (run_a2, "Change: raise C only. Interpretation: score improved."),
                    ]
                ),
            )

            report = build_comparison_report(
                root=root,
                agent_dirs=[agent_dir],
                benchmark_id="bench_a",
                model_family="svm",
            )

            self.assertEqual(len(report.agents), 1)
            self.assertEqual(report.agents[0].rounds[1].best_candidate, "c_high")

    def test_history_report_cli_writes_html_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_a1 = "20260406T010000000000Z-agent_alpha-bench_a"
            run_a2 = "20260406T020000000000Z-agent_alpha-bench_a"
            run_b1 = "20260406T010500000000Z-agent_beta-bench_a"
            run_b2 = "20260406T020500000000Z-agent_beta-bench_a"
            self.write_text(
                root / ".work" / "agents" / "agent_alpha" / "history.md",
                make_history(
                    [
                        f"| {run_a1} | bench_a | toy | control_a | svm | 0.100000 | 1 | sklearn | `.work/runs/a1.json` | control_a | 0.100000 | control_a | 0.100000 | agent_alpha | control_a | 0.100000 |",
                        f"| {run_a2} | bench_a | toy | c_high | svm | 0.160000 | 1 | sklearn | `.work/runs/a2.json` | c_high | 0.160000 | c_high | 0.160000 | agent_alpha | c_high | 0.160000 |",
                        f"| {run_a2} | bench_a | toy | c_low | svm | 0.120000 | 2 | sklearn | `.work/runs/a2.json` | c_high | 0.160000 | c_high | 0.160000 | agent_alpha | c_high | 0.160000 |",
                    ]
                ),
            )
            self.write_text(
                root / ".work" / "agents" / "agent_alpha" / "report.md",
                make_report(
                    [
                        (run_a1, "Hypothesis: start raw. Decision: establish baseline. Verdict: pending."),
                        (run_a2, "Change: raise C only. Why: baseline weak. Interpretation: score improved."),
                    ]
                ),
            )
            self.write_text(
                root / ".work" / "agents" / "agent_beta" / "history.md",
                make_history(
                    [
                        f"| {run_b1} | bench_a | toy | control_b | svm | 0.110000 | 1 | sklearn | `.work/runs/b1.json` | control_b | 0.110000 | control_b | 0.110000 | agent_beta | control_b | 0.110000 |",
                        f"| {run_b2} | bench_a | toy | scaled_b | svm | 0.150000 | 1 | sklearn | `.work/runs/b2.json` | scaled_b | 0.150000 | scaled_b | 0.150000 | agent_beta | scaled_b | 0.150000 |",
                        f"| {run_b2} | bench_a | toy | clipped_b | svm | 0.130000 | 2 | sklearn | `.work/runs/b2.json` | scaled_b | 0.150000 | scaled_b | 0.150000 | agent_beta | scaled_b | 0.150000 |",
                    ]
                ),
            )
            self.write_text(
                root / ".work" / "agents" / "agent_beta" / "report.md",
                make_report(
                    [
                        (run_b1, "Hypothesis: test normalization first. Decision: compare preprocessing. Verdict: pending."),
                        (run_b2, "Hypothesis: scaling helps. Decision: keep normalization. Verdict: supported."),
                    ]
                ),
            )

            output_dir = root / "tmp" / "history_report"
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "history-report",
                        "--root",
                        str(root),
                        "--agents",
                        "agents/agent_alpha",
                        "--agents",
                        "agents/agent_beta",
                        "--benchmark",
                        "bench_a",
                        "--model",
                        "svm",
                        "--output-dir",
                        str(output_dir),
                        "--title",
                        "Toy Report",
                    ]
                )

            self.assertEqual(exit_code, 0)
            html_path = output_dir / "index.html"
            json_path = output_dir / "report.json"
            self.assertTrue(html_path.exists())
            self.assertTrue(json_path.exists())

            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("Toy Report", html_text)
            self.assertIn("<svg", html_text)
            self.assertIn("agent_alpha", html_text)
            self.assertIn("keep normalization.", html_text)
            self.assertIn("Full Report", html_text)

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "Toy Report")
            self.assertEqual(payload["benchmark"], "bench_a")
            self.assertEqual(payload["model"], "svm")
            self.assertEqual(len(payload["agents"]), 2)
            self.assertEqual(payload["agents"][0]["rounds"][1]["best_candidate"], "c_high")


if __name__ == "__main__":
    unittest.main()
