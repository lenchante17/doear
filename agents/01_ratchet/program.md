# program.md

## Initial

- Read `autoresearch/backends.py` once when starting the run.
- If repo-native MLP controls may matter, also read `autoresearch/repo_mlp.py` once.
- If `policy.toml` enables advisors, run `python3 -m autoresearch advise --agent-dir agents/01_ratchet` and read `.work/agents/01_ratchet/advice/latest.md`.
- Read `.work/agents/01_ratchet/history.md`, `.work/agents/01_ratchet/report.md`, and `agents/01_ratchet/submission.toml` before starting.

## Initial Commands

1. `cat autoresearch/backends.py`
2. Optional: `cat autoresearch/repo_mlp.py`
3. Optional: `python3 -m autoresearch advise --agent-dir agents/01_ratchet`
4. Optional: `cat .work/agents/01_ratchet/advice/latest.md`
5. `cat .work/agents/01_ratchet/history.md`
6. `cat .work/agents/01_ratchet/report.md`
7. `cat agents/01_ratchet/submission.toml`

## Loop

- Read `history.md` and `report.md` before each round.
- If advisors are enabled, refresh `advice/latest.md` before editing `submission.toml`.
- Treat advisor recommendations as guidance, not as mandatory submissions; you may adapt, combine, or replace them with a novel config.
- Edit `submission.toml` for one small mutation around the current incumbent.
- Submit one round and read the updated `history.md`.
- Append a `## Run <run_id>` section to `report.md` with `Change: ...`, `Interpretation: ...`, `Decision: ...`, and `Next: ...`.
- Keep or discard the idea, then repeat as long as the run continues.
- Reveal hidden test only when ending the agent.

## Loop Commands

1. Optional: `python3 -m autoresearch advise --agent-dir agents/01_ratchet`
2. Optional: `cat .work/agents/01_ratchet/advice/latest.md`
3. `cat .work/agents/01_ratchet/history.md`
4. `cat .work/agents/01_ratchet/report.md`
5. Edit `agents/01_ratchet/submission.toml`
6. `python3 -m autoresearch run --agent-dir agents/01_ratchet`
7. `cat .work/agents/01_ratchet/history.md`
8. Append the new run section to `.work/agents/01_ratchet/report.md`
9. `python3 -m autoresearch finalize-agent --agent-dir agents/01_ratchet` only when ending the agent

## Search Strategy

- Start with a baseline if the history is empty.
- Treat the best validated candidate as the incumbent.
- Use each round as a tight keep-or-discard mutation around that incumbent.
- Prefer one primary mutation per run and queue nearby ablations, simplifications, or safer variants for later rounds.
- If the current neighborhood stalls, jump to a materially different idea.
