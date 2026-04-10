# program.md

## Initial

- Read `autoresearch/backends.py` once when starting the run.
- If repo-native MLP controls may matter, also read `autoresearch/repo_mlp.py` once.
- If `policy.toml` enables advisors, run `python3 -m autoresearch advise --agent-dir agents/02_screening_doe` and read `.work/agents/02_screening_doe/advice/latest.md`.
- Read `.work/agents/02_screening_doe/history.md`, `.work/agents/02_screening_doe/report.md`, and `agents/02_screening_doe/submission.toml` before starting.

## Initial Commands

1. `cat autoresearch/backends.py`
2. Optional: `cat autoresearch/repo_mlp.py`
3. Optional: `python3 -m autoresearch advise --agent-dir agents/02_screening_doe`
4. Optional: `cat .work/agents/02_screening_doe/advice/latest.md`
5. `cat .work/agents/02_screening_doe/history.md`
6. `cat .work/agents/02_screening_doe/report.md`
7. `cat agents/02_screening_doe/submission.toml`

## Loop

- Read `history.md` and `report.md` before each round.
- If advisors are enabled, refresh `advice/latest.md` before choosing the next screening contrast.
- Treat advisor recommendations as guidance, not as mandatory submissions; you may adapt, combine, or replace them with a novel config.
- Edit `submission.toml` to answer one screening question.
- Submit one round and read the updated `history.md`.
- Append a `## Run <run_id>` section to `report.md` with `Hypothesis: ...`, `Factors: ...`, `Levels: ...`, `Interpretation: ...`, `Decision: ...`, and `Next: ...`.
- Choose the next contrast, then repeat as long as the run continues.
- Reveal hidden test only when ending the agent.

## Loop Commands

1. Optional: `python3 -m autoresearch advise --agent-dir agents/02_screening_doe`
2. Optional: `cat .work/agents/02_screening_doe/advice/latest.md`
3. `cat .work/agents/02_screening_doe/history.md`
4. `cat .work/agents/02_screening_doe/report.md`
5. Edit `agents/02_screening_doe/submission.toml`
6. `python3 -m autoresearch run --agent-dir agents/02_screening_doe`
7. `cat .work/agents/02_screening_doe/history.md`
8. Append the new run section to `.work/agents/02_screening_doe/report.md`
9. `python3 -m autoresearch finalize-agent --agent-dir agents/02_screening_doe` only when ending the agent

## Search Strategy

- Treat each round as one clean screening question.
- Use one candidate per run and compare anchor versus treatment sequentially through `history.md` instead of expecting two candidate slots.
- Start broad across factor groups before doing local tuning.
- Hold nuisance factors fixed so the main effect stays attributable.
- If the current screening path stalls, reopen screening on neglected factors or a new anchor region.
