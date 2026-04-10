# program.md

## Initial

- Read `autoresearch/backends.py` once when starting the run.
- If repo-native MLP controls may matter, also read `autoresearch/repo_mlp.py` once.
- If `policy.toml` enables advisors, run `python3 -m autoresearch advise --agent-dir agents/03_advanced_doe` and read `.work/agents/03_advanced_doe/advice/latest.md`.
- Read `.work/agents/03_advanced_doe/history.md`, `.work/agents/03_advanced_doe/report.md`, and `agents/03_advanced_doe/submission.toml` before starting.

## Initial Commands

1. `cat autoresearch/backends.py`
2. Optional: `cat autoresearch/repo_mlp.py`
3. Optional: `python3 -m autoresearch advise --agent-dir agents/03_advanced_doe`
4. Optional: `cat .work/agents/03_advanced_doe/advice/latest.md`
5. `cat .work/agents/03_advanced_doe/history.md`
6. `cat .work/agents/03_advanced_doe/report.md`
7. `cat agents/03_advanced_doe/submission.toml`

## Loop

- Read `history.md` and `report.md` before each round and reconstruct the DOE state from both.
- If advisors are enabled, refresh `advice/latest.md` before choosing the next design question.
- Treat advisor recommendations as guidance, not as mandatory submissions; you may adapt, combine, or replace them with a novel config.
- Edit `submission.toml` for one design question.
- Submit one round and read the updated `history.md`.
- Append a `## Run <run_id>` section to `report.md` in this exact shape: `Stage: ...; Anchor: ...; Question: ...; Factors: ...; Levels: ...; Alias risk: ...; Prediction: ...; Observed signal: ...; Belief: ...; Decision: ...; Next: ...`
- Update the staged DOE plan, then repeat as long as the run continues.
- Reveal hidden test only when ending the agent.

## Loop Commands

1. Optional: `python3 -m autoresearch advise --agent-dir agents/03_advanced_doe`
2. Optional: `cat .work/agents/03_advanced_doe/advice/latest.md`
3. `cat .work/agents/03_advanced_doe/history.md`
4. `cat .work/agents/03_advanced_doe/report.md`
5. Edit `agents/03_advanced_doe/submission.toml`
6. `python3 -m autoresearch run --agent-dir agents/03_advanced_doe`
7. `cat .work/agents/03_advanced_doe/history.md`
8. Append the new run section to `.work/agents/03_advanced_doe/report.md`
9. `python3 -m autoresearch finalize-agent --agent-dir agents/03_advanced_doe` only when ending the agent

## Search Strategy

- Run a staged DOE program: screening, then interaction checks, then local refinement.
- Use one candidate for the current anchor-or-treatment question and compare against prior rounds instead of expecting two fresh points in one run.
- Prefer contrasts that separate effects cleanly and use foldover or orthogonal follow-up when a result is aliased or ambiguous.
- Spend later rounds only on factors that showed evidence during screening.
- If the current DOE path stalls, reopen screening, run a deliberate interaction check, or reset around a different anchor.
