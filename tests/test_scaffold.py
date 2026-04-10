from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autoresearch.scaffold import scaffold_agent


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_agent_defaults_to_cifar10_real(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = scaffold_agent(root, "default_agent", "exploit")

            submission_text = (agent_dir / "submission.toml").read_text(encoding="utf-8")
            instructions_text = (agent_dir / "program.md").read_text(encoding="utf-8")
            policy_text = (agent_dir / "policy.toml").read_text(encoding="utf-8")

            self.assertIn('benchmark = "cifar10_real"', submission_text)
            self.assertIn('backend = "sklearn"', submission_text)
            self.assertIn('model_family = "mlp"', submission_text)
            self.assertEqual(submission_text.count('model_family = "mlp"'), 1)
            self.assertNotIn('model_family = "svm"', submission_text)
            self.assertNotIn("notes =", submission_text)
            self.assertIn('mode = "agent"', policy_text)
            self.assertIn('agent_profile = "01_ratchet"', policy_text)
            self.assertIn("advisors = []", policy_text)
            self.assertIn(".work/agents/default_agent/history.md", instructions_text)
            self.assertIn(".work/agents/default_agent/report.md", instructions_text)
            self.assertIn(".work/agents/default_agent/advice/latest.md", instructions_text)
            self.assertIn("autoresearch/backends.py", instructions_text)
            self.assertIn("autoresearch/repo_mlp.py", instructions_text)
            self.assertIn("python3 -m autoresearch advise --agent-dir agents/default_agent", instructions_text)
            self.assertIn("python3 -m autoresearch run --agent-dir agents/default_agent", instructions_text)
            self.assertFalse((agent_dir / "AGENTS.md").exists())
            self.assertFalse((agent_dir / "history.md").exists())
            self.assertTrue((root / ".work" / "agents" / "default_agent" / "history.md").exists())
            self.assertTrue((root / ".work" / "agents" / "default_agent" / "report.md").exists())
            self.assertNotIn("feedback.md", instructions_text)
            self.assertFalse((agent_dir / "feedback.md").exists())

    def test_scaffold_agent_supports_numeric_profile_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = scaffold_agent(root, "screening_condition", "02")

            policy_text = (agent_dir / "policy.toml").read_text(encoding="utf-8")
            instructions_text = (agent_dir / "program.md").read_text(encoding="utf-8")

            self.assertIn('agent_profile = "02_screening_doe"', policy_text)
            self.assertIn("choosing the next screening contrast", instructions_text)
            self.assertIn("agents/screening_condition/submission.toml", instructions_text)
            self.assertNotIn("agents/02_screening_doe/submission.toml", instructions_text)


if __name__ == "__main__":
    unittest.main()
