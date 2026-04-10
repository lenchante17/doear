from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autoresearch.policy import PolicyLoadError, load_policy


class PolicyTests(unittest.TestCase):
    def write_text(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents.strip() + "\n", encoding="utf-8")

    def test_load_policy_normalizes_numeric_agent_profile_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "agent_optuna"
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "agent"
agent_profile = "03"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp.toml"
""",
            )

            policy = load_policy(root, agent_dir)

            self.assertEqual(policy.agent_profile, "03_advanced_doe")

    def test_direct_policy_rejects_agent_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "optuna_direct"
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "direct"
agent_profile = "01"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp.toml"
""",
            )

            with self.assertRaises(PolicyLoadError):
                load_policy(root, agent_dir)


if __name__ == "__main__":
    unittest.main()
