---
marp: true
theme: beam
paginate: true
size: 16:9
title: AutoML에서 Autoresearch로
description: DOE를 Research Agent의 Harness로 제안하는 발표 초안
---

<!-- _class: title -->
<!-- footer: "" -->

# AutoML에서 Autoresearch로

DOE는 Research Agent의 Harness가 될 수 있는가?

AutoML, Autoresearch, MLOps, DOE-guided Agent

실험 결과 영역은 이후 채움

---
<!-- footer: "핵심 질문: Research Agent를 믿게 만드는 harness는 무엇인가?" -->

## 1. 왜 지금 이 주제인가?

- Coding Agent는 실제 개발 workflow 안에서 빠르게 발전하고 있다.
- Research automation도 문헌 정리, 코드 수정, 실험 실행, 보고서 작성까지 넓어지고 있다.
- 하지만 연구 실험은 여전히 ad hoc 반복으로 흐르기 쉽다.
- 이제 질문은 "agent가 실험을 돌릴 수 있는가?"보다 "무슨 harness가 agent를 더 신뢰 가능하게 만드는가?"이다.

| 지금 보이는 변화 | 아직 약한 부분 |
| --- | --- |
| Coding Agent의 실제 배포 | research loop의 규율 |
| 실험 자동화 도구 증가 | 실험 설계 표준 |
| end-to-end research demo 확산 | robustness / reproducibility |

---
<!-- footer: "AutoML은 비교적 정해진 search space 안을 최적화한다." -->

## 2. AutoML이란 무엇인가?

- AutoML은 모델 개발 과정의 일부 탐색을 자동화한다.
- 대표 대상은 `model selection`, `hyperparameter tuning`, `pipeline search`다.
- 더 넓게는 `feature engineering`과 `NAS`까지 확장된다.
- 핵심은 비교적 주어진 `search space` 안에서 성능을 최적화하는 것이다.

`Data → Search over models/pipelines → Evaluation → Best configuration`

---
<!-- footer: "Autoresearch는 config보다 더 넓은 연구 행위를 탐색 대상으로 삼는다." -->

## 3. Autoresearch란 무엇인가?

- Autoresearch는 단순한 `hyperparameter search`를 넘는다.
- `code`, `module`, `pipeline structure`, `experiment program`까지 수정할 수 있다.
- `tool use`, `memory`, `literature`, `iterative reasoning`을 함께 사용할 수 있다.
- 따라서 `search space`는 AutoML보다 넓고, 덜 정돈되어 있으며, 더 open-ended하다.

| AutoML | Autoresearch |
| --- | --- |
| config / architecture 중심 | hypothesis / code / module / pipeline |
| explicit objective 최적화 | objective + reasoning + iteration |

---
<!-- footer: "넓어진 search space는 더 강한 behavioral constraint를 요구한다." -->

## 4. AutoML vs. Autoresearch

| 항목 | AutoML | Autoresearch |
| --- | --- | --- |
| 탐색 대상 | config, architecture | hypothesis, code, module, pipeline, experiment program |
| 평가 | explicit objective | objective + reasoning + iteration |
| 인간 역할 | search space 설계 | research program 설계 |
| 주요 위험 | 비효율적 탐색 | metric hacking, incoherent search |
| 필요한 인프라 | experiment infra | experiment + memory + harness |

---
<!-- _class: tinytext -->
<!-- footer: "사용례는 curated repo들에 등장하는 실제 task 유형을 요약한 것이다." -->

## 5. 현재 보이는 사용례

| 연구 작업 | 이미 자동화되는 형태 |
| --- | --- |
| 문헌 조사 | 논문 검색, 요약, citation 포함 report 생성 |
| idea exploration | novelty check, idea refinement, proposal structuring |
| paper-to-code | 논문 구현, baseline reproduction, Kaggle/quant task automation |
| experiment execution | 코드 수정, run, metric 비교, keep-or-revert loop |
| 결과 해석 | failure analysis, robustness check, 비교 요약 |
| 글쓰기 보조 | manuscript draft, figure/diagram 제작, reviewer response 초안 |

- 즉 "연구 자동화"는 이미 단일 단계가 아니라 정보 수집부터 실험, 보고서까지 여러 단계에 걸쳐 나타난다.

---
<!-- _class: tinytext -->
<!-- footer: "발전 방향은 ecosystem이 지금 어떤 층으로 두터워지는지를 요약한다." -->

## 6. 지금 보이는 발전 방향

| 방향 | 의미 |
| --- | --- |
| end-to-end 통합 | topic에서 paper까지 한 loop로 묶으려는 시도 |
| Coding Agent와 결합 | experiment 실행층을 coding agent가 담당 |
| reusable skills / plugins | domain별 workflow를 재사용 가능한 모듈로 분리 |
| benchmark 강화 | 성능뿐 아니라 robustness와 open-endedness 평가 |
| infra diversification | single GPU, consumer desktop, WebGPU, swarm 실행 |
| persistent memory / portfolio | 실험 기록을 장기 지식과 탐색 정책으로 재사용 |

- 다시 말해 Autoresearch는 "한 번의 인상적인 demo"에서 "programmable research stack"으로 이동 중이다.

---
<!-- footer: "MLOps는 AutoML 뒤에 붙는 부속물이 아니라 자동화를 가능하게 하는 공통 기반이다." -->

## 7. 자동화를 가능하게 하는 공통 기반: MLOps

- AutoML이든 Autoresearch든 자동화를 반복 가능하게 만들려면 실행 인프라가 필요하다.
- `experiment tracking`, `orchestration`, `reproducibility`가 있어야 탐색이 지식으로 남는다.
- `artifact 관리`, `registry`, `monitoring`, `cost governance`가 있어야 자동화가 운영 가능해진다.
- 즉 `MLOps`는 AutoML의 뒤처리가 아니라, 둘 다를 떠받치는 공통 substrate에 가깝다.

| 공통 인프라 | AutoML에서의 역할 | Autoresearch에서의 역할 |
| --- | --- | --- |
| tracking | 후보 비교 | 실험 history 축적 |
| orchestration | search job 실행 | multi-step agent loop 실행 |
| reproducibility | 재실행 / 검증 | hypothesis와 edit 검증 |
| cost governance | budget control | long-horizon research budget 관리 |

---
<!-- _class: title -->
<!-- footer: "Prelim 종료: 이제부터는 harness와 DOE가 본론이다." -->

# Prelim 정리

여기까지는 배경이다.

이제 핵심 질문은
`Research Agent에 어떤 harness가 필요한가?`이다.

---
<!-- footer: "Coding Agent를 믿게 만든 것은 모델만이 아니라 harness였다." -->

## 8. Harness gap

| Coding Agent 쪽에서 이미 흔한 것 | Research Agent 쪽에서 아직 약한 것 |
| --- | --- |
| `TDD` | hypothesis discipline |
| `CI` | factor definition |
| regression test | robustness check |
| lint / build check | reproducible iteration structure |
| deploy guardrail | experiment promotion rule |

- 그래서 Research Agent는 점수가 좋아 보여도 그 탐색이 coherent했는지 설명하기 어렵다.

---
<!-- footer: "DOE를 통계 기법이 아니라 agent 운영 규율로 본다." -->

## 9. DOE를 Harness 후보로 보기

| DOE primitive | Agent loop에서의 역할 |
| --- | --- |
| screening | 중요한 factor를 초기에 좁힘 |
| factorial thinking | interaction을 구조적으로 확인 |
| sequential refinement | 유망 구간을 단계적으로 세밀화 |
| robustness / confirmation | 우연한 win과 재현 가능한 win을 분리 |

- 따라서 DOE는 "무엇을, 어떤 순서로, 어떤 조합으로 실험할지"에 대한 규율을 제공한다.

---
<!-- footer: "점수만이 아니라 experiment ordering과 interpretation 구조가 달라진다." -->

## 10. Agent loop에 무엇이 달라지는가?

| 단계 | Vanilla Agent | DOE-guided Agent |
| --- | --- | --- |
| 시작 | idea 생성 | factor 정의 |
| 초반 | code change 후 바로 run | screening으로 후보 압축 |
| 중반 | gain이 나면 계속 추적 | interaction check |
| 후반 | best-so-far 갱신 중심 | refinement + robustness |
| 종료 | score가 높으면 채택 | promote rule로 승격 |

---
<!-- footer: "이 비교는 prompt wording이 아니라 harness 설계 비교다." -->

## 11. 실험 설정

| Variant | 설명 | 비교 목적 |
| --- | --- | --- |
| Vanilla Agent | unconstrained iterative experiments | 기본 baseline |
| DOE Agent | DOE 기반 planning과 staging | harness 효과 측정 |
| DOE + X Agent | DOE + 추가 전략 모듈 | harness와 추가 전략의 결합 효과 |

- 평가는 `best score`만이 아니라 `cost`, `robustness`, `portfolio behavior`까지 함께 본다.

---
<!-- footer: "결과 표는 성능, 비용, 안정성을 함께 보여줘야 한다." -->

## 12. 결과 요약

- Placeholder only: 실험 완료 후 채움

| Variant | Best score | Avg improvement | Runs | Cost | Robustness pass |
| --- | --- | --- | --- | --- | --- |
| Vanilla | TBD | TBD | TBD | TBD | TBD |
| DOE | TBD | TBD | TBD | TBD | TBD |
| DOE + X | TBD | TBD | TBD | TBD | TBD |

---
<!-- footer: "최종 점수보다 learning dynamics의 차이를 보여주는 그래프다." -->

## 13. 성능 향상 추이

- Placeholder only: 실험 완료 후 채움
- `experiment budget` 또는 `run count` 대비 `best-so-far metric`
- 수렴 속도, plateau 형태, sample efficiency 비교

`x-axis = budget / run count`

`y-axis = best-so-far metric`

---
<!-- footer: "DOE의 가치는 headline score보다 탐색의 질 변화에 있다." -->

## 14. 실험 포트폴리오 또는 실패 구조

- Placeholder only: 실험 완료 후 채움
- Option A: `Tic / Tac / To` 비율
- Option B: `invalid / no gain / unstable / robustness fail / promoted`
- Option C: `information gain vs. performance gain`

---
<!-- footer: "숫자 해석은 agent behavior와 experiment program 변화로 연결돼야 한다." -->

## 15. 왜 DOE-guided Agent는 다를 수 있는가?

- `search space`가 더 구조화된다.
- 중복되거나 정보량이 낮은 실험이 줄어든다.
- 상호작용을 우연히가 아니라 의도적으로 본다.
- opportunistic improvement와 robustness 확인을 분리할 수 있다.
- experiment history가 재사용 가능한 지식으로 축적된다.

---
<!-- _class: tinytext -->
<!-- footer: "문헌 조사, 가설 수립 같은 단계는 DOE의 바깥 또는 상위 층에 더 가깝다." -->

## 16. 대학원 연구 루프와 DOE의 범위

| 연구 루프 단계 | DOE가 직접 다루는 정도 |
| --- | --- |
| 문헌 조사 | 약함 |
| 가설 수립 | 약함 |
| 실험 설계 | 강함 |
| 구현 및 실행 | 중간, 인프라 필요 |
| 분석 | 중간 |
| 토론 및 수정 | 간접적 |
| 다음 실험 선택 | 강함 |

- 즉 DOE는 `research loop` 전체를 대체하기보다, 그중에서도 `experiment design / comparison / refinement`를 강하게 규율하는 도구에 가깝다.

---
<!-- footer: "DOE는 강한 후보이지만 만능 해법은 아니다." -->

## 17. 한계

- DOE가 `literature review`나 `hypothesis generation` 자체를 대체하진 못한다.
- open-ended research space는 깔끔한 factorization이 어렵다.
- large-scale training에서는 replication 비용이 크다.
- classical DOE는 discrete structural edit 공간에 그대로 맞지 않을 수 있다.
- evaluation harness가 약하면 DOE도 쉽게 흔들린다.

---
<!-- footer: "마지막 메시지는 better agents보다 better harnesses다." -->

## 18. 결론

- AutoML에서 Autoresearch로 갈수록 `search space`는 넓어진다.
- search space가 넓어질수록 더 강한 `harness`가 필요하다.
- DOE는 Research Agent의 experimentation harness로 매우 유력한 후보다.

> 다음 단계는 더 좋은 agent 자체보다 더 좋은 harness이다.

---
<!-- _class: tinytext -->
<!-- footer: "웹 기반 사례와 분류는 2026-04-07 기준" -->

## 19. References

| 구분 | 예시 |
| --- | --- |
| curated landscape | `alvinreal/awesome-autoresearch`, `handsome-rich/Awesome-Auto-Research-Tools` |
| end-to-end systems | `karpathy/autoresearch`, `microsoft/RD-Agent`, `SakanaAI/AI-Scientist` |
| deep research | `assafelovic/gpt-researcher`, `Open Deep Research`, `PaperQA2` |
| experiment/code agents | `OpenHands`, `Aider`, `SWE-agent`, `AIDE` |
| evaluation | `openai/mle-bench`, `snap-stanford/MLAgentBench`, `chchenhui/mlrbench` |
