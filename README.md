# Autoresearch Harness

이 저장소는 AutoML 후보 제안 정책을 비교하기 위한 하네스다. 기본 DOE 에이전트 실험뿐 아니라 optimizer direct recommendation과 optimizer advisory를 받은 agent 실험을 같은 레일 위에서 비교한다.

핵심 계약:

- 각 실험 디렉터리 `agents/<condition_name>/`는 하나의 condition이다. condition은 agent-mediated일 수도 있고 direct recommendation일 수도 있다.
- agent-mediated condition은 `policy.toml`의 `agent_profile`로 `01_ratchet`, `02_screening_doe`, `03_advanced_doe` 중 하나를 고른다.
- shipped benchmark는 모두 `mlp` family만 허용한다.
- 실제 `run` 평가는 현재 `submission.toml`의 검증된 단일 candidate만 본다.
- optimizer는 `advise` 단계에서 snapshot을 만들고, direct condition은 그 snapshot에서 아직 평가하지 않은 candidate 하나를 골라 `submission.toml`을 자동 생성한다.
- agent condition은 `.work/agents/<condition_name>/advice/latest.md`와 snapshot json을 읽고 다음에 제출할 단일 candidate를 `submission.toml`에 쓴다.
- `program.md`는 `policy.toml`의 `agent_profile`에서 materialize되는 작업 지침이다.
- 해석, 판단, 다음 계획은 `.work/agents/<condition_name>/report.md`에 남긴다.
- 탐색 중에는 validation 결과만 본다.
- hidden test는 종료 시 `finalize-agent`에서만 공개된다.
- `.work/agents/<condition_name>/history.md`는 runner가 쌓는 score ledger다.

## Pipeline

### 1. Start

각 condition은 먼저 아래 파일을 확인한다.

- `agents/<condition_name>/policy.toml`
- `agents/<condition_name>/program.md`
- `.work/agents/<condition_name>/history.md`
- `.work/agents/<condition_name>/report.md`
- 필요하면 `agents/<condition_name>/submission.toml`
- `autoresearch/backends.py`
- 필요하면 `autoresearch/repo_mlp.py`

실제 학습 코드는 읽기 전용이다.

### 2. Loop

한 라운드의 작업은 항상 같다.

1. 필요하면 먼저 advisor snapshot을 만든다.

```bash
python3 -m autoresearch advise --agent-dir agents/<condition_name>
```

2. direct condition이면 `advise`가 아직 평가하지 않은 candidate 하나로 `submission.toml`을 자동 생성한다.
3. agent condition이면 `.work/agents/<condition_name>/advice/latest.md`와 snapshot json을 읽고 다음 단일 candidate로 `submission.toml`을 갱신한다.
4. 아래 명령으로 제출한다.

```bash
python3 -m autoresearch run --agent-dir agents/<condition_name>
```

5. 새 validation 결과 요약은 `.work/agents/<condition_name>/history.md`에 누적된다.
6. 방금 실행한 `run_id`를 기준으로 `.work/agents/<condition_name>/report.md`에 해석을 추가한다.
7. 다음 라운드는 `history.md`, `report.md`, `advice/latest.md`를 같이 읽고 이어간다.

대표적으로 비교하려는 condition archetype:

- `optuna_direct`
- `smac3_direct`
- `agent_plain`
- `agent_optuna`
- `agent_smac3`
- `agent_optuna_smac3`

공통적으로 `.work/agents/<condition_name>/history.md`는 runner-owned ledger이고 `.work/agents/<condition_name>/report.md`는 agent-owned lab notebook이다. direct condition도 같은 ledger를 쓰지만 `policy.toml`의 `mode = "direct"`가 provenance를 구분한다.

agent condition은 아래처럼 01/02/03 profile을 선택할 수 있다.

```toml
mode = "agent"
agent_profile = "02"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_advisory_v1.toml"
```

여기서 `proposal_count`는 advisor snapshot에 담을 recommendation 수다. 현재 `run`은 그중 하나만 평가한다.

### 3. End

탐색을 끝낼 때만 hidden test를 공개한다.

```bash
python3 -m autoresearch finalize-agent --agent-dir agents/<condition_name>
```

최종 결과는 `.work/leaderboard.md`, `.work/finalized/*.json`, `.work/agents/<condition_name>/final_report.md`에 반영된다.

## Files

- `agents/<condition_name>/policy.toml`: condition mode, optional `agent_profile`, advisors, advisor recommendation count인 `proposal_count`, search_space
- `agents/<condition_name>/program.md`: `agent_profile`에서 materialize된 agent condition용 전략 지침
- `agents/<condition_name>/submission.toml`: 현재 round에서 평가할 단일 candidate 제출안 또는 direct condition이 자동 생성한 제출안
- `experiments/search_spaces/*.toml`: advisor가 샘플링하는 config space
- `.work/agents/<condition_name>/advice/latest.md`: 최신 advisor 요약
- `.work/agents/<condition_name>/advice/*.json`: advisor snapshot 원본
- `.work/agents/<condition_name>/history.md`: 누적 실험 ledger와 aggregate best-val 상태
- `.work/agents/<condition_name>/report.md`: 가설, 해석, 의사결정, 다음 액션
- `.work/leaderboard.md`: validation/test 결과 표

## Commands

```bash
python3 -m autoresearch list-benchmarks
python3 -m autoresearch advise --agent-dir agents/01_ratchet
python3 -m autoresearch run --agent-dir agents/01_ratchet
python3 -m autoresearch finalize-agent --agent-dir agents/01_ratchet
python3 -m autoresearch init-agent --name cautious_sweeper --strategy 03
```

## Notes

- benchmark catalog에는 `max_candidates_per_submission = 2`가 남아 있지만, 현재 harness의 `run` 경로는 round당 정확히 `1` candidate만 평가한다.
- direct/advisory condition도 advisor snapshot에서는 여러 recommendation을 만들 수 있지만, 실제 제출은 항상 단일 candidate로 축약된다.
- shipped benchmark의 탐색 family는 `mlp`로 고정한다.
- 모델 선택은 validation으로만 하고, test는 종료 후 확인용으로 분리한다.
- `submission.toml`의 top-level narrative key는 허용하지 않는다. 해석과 메모는 `report.md`에 둔다.
- `optuna`와 `smac3` integration은 optional dependency다. 설치되지 않았으면 해당 advisor를 호출할 때 명시적으로 실패한다.
- advisor snapshot provenance는 artifact와 history에 함께 남는다. direct와 agent-assisted 조건은 같은 evaluator를 공유하고 proposer/decider만 바뀐다.
