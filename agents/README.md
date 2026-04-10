# Agents

`agents/` 아래 디렉터리는 이제 좁게는 agent, 넓게는 experiment condition이다. 일부는 사람이/LLM이 `submission.toml`을 쓰는 condition이고, 일부는 advisor snapshot이 단일 candidate 제출안을 직접 만드는 direct condition이다.

현재 active agent 디렉터리는 `01_ratchet`, `02_screening_doe`, `03_advanced_doe`다.

agent-mediated condition은 `policy.toml`에서 아래 세 profile 중 하나를 선택한다.

- `01_ratchet`
- `02_screening_doe`
- `03_advanced_doe`

공통 규칙:

- 코드는 건드리지 않고 평가 대상 candidate config는 항상 `submission.toml`의 단일 candidate로만 둔다.
- `policy.toml`이 advisor를 켜면 먼저 `python3 -m autoresearch advise --agent-dir agents/<condition_name>`를 실행한다.
- `policy.toml`에 `agent_profile`이 있으면 `program.md`는 그 profile의 materialized instruction view로 취급한다.
- `.work/agents/<agent_name>/advice/latest.md`와 snapshot json은 agent가 읽는 advisory input이다.
- `.work/agents/<agent_name>/history.md`와 `.work/agents/<agent_name>/report.md`를 읽고 다음 후보를 정한다.
- `.work/agents/<agent_name>/history.md`는 runner가 쓰는 결과 ledger다.
- `.work/agents/<agent_name>/report.md`는 agent가 쓰는 분석 notebook이다.
- 한 라운드를 마치면 `run_id` 기준으로 `report.md`에 가설, 해석, 판단, 다음 액션을 append한다.
- 각 새 작업 구간의 시작에서 실제 학습이 수행되는 코드를 한 번 읽는다. 기본 읽기 대상은 `autoresearch/backends.py`이고, repo-native MLP 경로를 열 가능성이 있으면 `autoresearch/repo_mlp.py`도 함께 읽는다.
- `autoresearch/backends.py`, `autoresearch/repo_mlp.py`, 벤치마크 카탈로그와 러너 코드는 읽기 전용이다. agent는 이 파일들을 수정하지 않는다.
- 제출은 `python3 -m autoresearch run --agent-dir agents/<agent_name>`로 실행하고, 현재 러너는 매 round 정확히 한 candidate만 받는다.
- direct condition은 `advise`가 아직 평가하지 않은 recommendation 하나로 `submission.toml`을 자동 생성하고, agent condition은 agent가 다음 단일 제출안을 고친다.
- `proposal_count`는 advisor snapshot에 담는 recommendation 수이지 동시 제출 슬롯 수가 아니다.
- 각 작업 구간은 새 subagent가 맡고, 다음 작업 구간은 이전 작업 구간의 로컬 파일만 읽고 이어받는다. 연속성은 `.work/agents/<agent_name>/history.md`와 `.work/agents/<agent_name>/report.md`로 복원하고, 현재 `submission.toml`은 다음 제안을 쓸 작업 사본으로만 취급한다.
- 작업 구간 사이에 구두 맥락이나 외부 메모를 넘기지 않는다. 다음 작업 구간이 볼 수 있는 것은 로컬 파일에 남은 기록뿐이다.
- 한 작업 구간을 끝낼 때는 filler round를 넣지 말고 종료한다. 다음 작업 구간이 다시 계획을 세운다.
- shipped benchmark에서는 모델을 `mlp`만 사용한다.
- 탐색 중에는 validation 결과만 공개된다.
- hidden test 결과는 agent 종료 후 `finalize-agent` 단계에서만 나온다.
- 같은 candidate나 같은 비교쌍을 반복 제출하지 않는다. 예외는 명시적인 confirmation round뿐이다.
- backend/runtime compatibility fix는 한 번의 setup round로 처리하고, 그 뒤에는 다시 실제 탐색으로 복귀한다.
- 개선이 장기간 멈추면 reset한다.

세부 탐색 전략은 공통 README에 두지 않고 각 condition 디렉터리의 `program.md`와 `policy.toml`에 둔다.
