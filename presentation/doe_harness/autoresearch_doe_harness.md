---
marp: true
theme: beam
paginate: true
size: 16:9
title: AutoML, Autoresearch, MLOps +@
description: DOE를 Research Agent의 Harness로 제안하는 발표 초안
---

<!-- _class: title -->
<!-- footer: "" -->

# AutoML, Autoresearch, MLOps +@

26.4.8

서민교

---
<!-- footer: "AutoML 시작" -->

## 1. AutoML이란 무엇인가?

- 모델 개발 탐색 일부 자동화
- 대표 대상: `model selection`, `hyperparameter tuning`, `pipeline search`
- 핵심: 비교적 주어진 `search space` 안 최적 설정 탐색

![w:950](./assets/automl_intro.jpeg)

---
<!-- footer: "NAS" -->

## 2. `Neural Architecture Search`는 AutoML의 확장이다

- parameter 대신 architecture 탐색
- AutoML의 `더 넓은 search space` 확장선
- 그래도 중심은 여전히 모델/파이프라인 후보 탐색

![w:900](./assets/nas_intro.jpg)

`hyperparameter search → pipeline search → architecture search`

---
<!-- footer: "Autoresearch의 등장" -->

## 3. `Autoresearch`는 어떻게 등장했고 무엇이 다른가?

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch): 작은 training setup 위 `read → edit → run → keep-or-revert` loop 제시
- 연구 workflow 일부를 agent가 직접 수행하며, 설정 탐색을 넘어 `code`, `module`, `experiment` 자체 수정
- AutoML의 `fixed search space` 바깥으로 확장
- 이후 [RD-Agent](https://github.com/microsoft/RD-Agent), [AI-Scientist](https://github.com/SakanaAI/AI-Scientist), [GPT Researcher](https://github.com/assafelovic/gpt-researcher) 등으로 빠르게 확장

---
<!-- footer: "작업 흐름" -->

## 4. Agent 작업 흐름

- 코드 읽기, baseline 파악
- 작은 가설 하나 선택
- 학습 코드나 설정 수정
- 짧은 실험 실행, metric 확인
- 나쁘면 revert, 의미 있으면 keep
- 핵심: `edit 한 번`이 아니라 `짧은 실험 loop의 누적`

`Question → Read → Edit → Run → Analyze → Next experiment`

---
<!-- footer: "핵심 차이" -->

## 5. AutoML vs. Autoresearch

| 항목 | AutoML | Autoresearch |
| --- | --- | --- |
| 탐색 대상 | config, pipeline, architecture | hypothesis, code, module, experiment |
| 핵심 질문 | 어떤 설정이 가장 좋은가 | 다음에 어떤 실험을 해야 하는가 |
| edit 단위 | parameter / architecture | code / module / pipeline / experiment |
| 평가 방식 | objective 중심 | objective + reasoning + iteration |
| 위험 | 비효율적 탐색 | incoherent search, metric hacking |
| 필요한 인프라 | experiment infra | experiment + memory + harness |

---
<!-- footer: "사용례와 확장" -->

## 6. 사용례와 확장

사용례
- 문헌 조사 / deep research: [GPT Researcher](https://github.com/assafelovic/gpt-researcher)
- 코드 수정 + 실험 반복: [karpathy/autoresearch](https://github.com/karpathy/autoresearch), [RD-Agent](https://github.com/microsoft/RD-Agent)
- end-to-end 연구 자동화: [AI-Scientist](https://github.com/SakanaAI/AI-Scientist)

확장
- benchmark / evaluation: [MLE-bench](https://github.com/openai/mle-bench), [MLAgentBench](https://github.com/snap-stanford/MLAgentBench), [MLR-Bench](https://github.com/chchenhui/mlrbench)
- plugin / skill 생태계: [awesome-autoresearch](https://github.com/alvinreal/awesome-autoresearch), [Awesome Auto Research Tools](https://github.com/handsome-rich/Awesome-Auto-Research-Tools)
- memory, reusable modules, hardware fork

---
<!-- footer: "실험 관리 필요" -->

## 7. 체계적인 실험 관리의 필요

- 공통 문제: `많은 run` 비교와 누적
- 필수 요소: `tracking`, `lineage`, `orchestration`
- agent edit가 들어오면 `artifact`, `promotion`, `monitoring`, `cost control` 중요도 상승
- 결국 운영 문제

---
<!-- footer: "핵심 MLOps 요소" -->

## 8. AutoML과 Autoresearch가 공통으로 요구하는 MLOps 요소

| 요소 | AutoML에서의 역할 | Autoresearch에서의 역할 |
| --- | --- | --- |
| tracking | sweep 비교 | hypothesis / code edit history 비교 |
| orchestration | search job 실행 | agent + eval job 실행 |
| registry / lineage | best model 승격 | experiment / prompt / code provenance 보존 |
| monitoring / cost | retrain trigger, SLO | budget, drift, unsafe promotion guardrail |

---
<!-- footer: "Kubeflow lifecycle" -->

## 9. MLOps는 모델 개발, 관리, 배포 파이프라인을 유지 관리하는 작업이다

![w:880](./assets/mlops_kubeflow.svg)

- Autoresearch loop는 이 큰 ML lifecycle 안의 일부
- 실제 시스템: `data`, `experiment`, `model registry`, `deployment`, `monitoring`
- 핵심 역할: `지속 운영`, `추적`, `승격`, `유지관리`

---
<!-- footer: "큰 질문" -->

## 10. 오늘의 큰 질문 두 가지

1. `Autoresearch`는 기존 `AutoML` 도메인을 AutoML 기법들에 비해 잘 푸는가?
2. `Autoresearch`에 어떤 harness를 적용하는 게 좋은가?

- 질문 1은 `capability comparison`
- 질문 2는 `operating policy / harness design`
- 오늘 발표는 이 두 질문을 분리해서 본다.

---
<!-- footer: "Question 1 / Optuna" -->

## 11. 질문 1: 비교 기준으로 왜 `Optuna TPE`를 보나

- `Optuna`의 `TPESampler`는 대표적인 hyperparameter optimization baseline이다.
- 좋은 trial 집합과 나머지 trial 집합의 density를 따로 모델링하고, 그 비율이 큰 쪽을 우선 제안한다.
- bounded search space에서 강한 incumbent exploitation을 보여 주기 쉽다.
- 따라서 같은 AutoML search space에서 `Autoresearch`가 이 baseline보다 더 잘 푸는지가 첫 질문이다.

---
<!-- footer: "Question 1 / SMAC3" -->

## 12. 질문 1: 비교 기준으로 왜 `SMAC3`를 보나

- `SMAC3`는 algorithm configuration과 hyperparameter optimization을 위한 대표적 Bayesian optimization baseline이다.
- surrogate model과 aggressive racing을 결합해 유망한 configuration에 평가 예산을 집중한다.
- mixed, categorical, conditional search space에서 자주 쓰이는 강한 비교 기준이다.
- 따라서 `Autoresearch`가 local search를 넘어선다면 이 baseline 대비 장점이 드러나야 한다.

---
<!-- footer: "Question 1 / Results" -->

## 13. 질문 1 실험 결과

**TBD**

- 현재 `Autoresearch`, `Optuna TPE`, `SMAC3` 비교 실험 진행 중
- 같은 bounded search space, 같은 benchmark, 같은 budget 기준으로 정리 예정

---
<!-- footer: "Question 2" -->

## 14. 질문 2: `Autoresearch`에 어떤 Harness를 적용할까?

- 질문 1이 `누가 더 잘 푸는가`라면, 질문 2는 `agent를 어떻게 운영해야 하는가`다.
- 여기부터는 `Autoresearch` 내부 운영 정책과 harness 설계를 본다.
- 아래 실험은 `DoE-guided harness`가 agent loop를 더 구조화할 수 있는지에 대한 답이다.

---
<!-- footer: "왜 Harness인가" -->

## 15. 왜 Harness 질문이 생기나

- 실험이 즉흥적으로 이어지기 쉬움
- 왜 이 실험을 했는지 attribution이 약함
- 큰 수정, 작은 튜닝, 검증 실험이 섞이기 쉬움
- robustness, replication, interaction 확인이 뒤로 밀림
- 잘 정리된 random search로 퇴화할 위험

---
<!-- footer: "좋은 Harness" -->

## 16. 어떤 Harness가 필요한가

- 무엇을 먼저 볼지 정하는 우선순위
- 어떤 조합을 함께 볼지 정하는 규율
- 탐색 단계와 검증 단계 분리
- 작은 수정과 큰 수정을 다르게 다루는 운영 규칙
- 실패도 정보로 남기는 구조
- 다음 라운드를 설계하는 순차 실험 체계

---
<!-- footer: "DoE 개념" -->

## 17. Design of Experiments(DoE)란 무엇인가

- 여러 요인을 한 번에 바꿔 보며 effect를 읽는 실험 설계
- 한 번의 최고점보다 `요인`, `상호작용`, `안정성` 파악에 강점
- 핵심 질문: 무엇을 바꿨고, 무엇이 실제로 영향을 줬는가

![h:330](./assets/doe_cake.png)

---
<!-- footer: "빌려오는 DoE 개념" -->

## 18. DoE에서 빌려오는 개념

- `screening`: 중요한 요인부터 좁히기
- `factorial thinking`: interaction 보기
- `sequential design`: 라운드별 정교화
- `robust design`: 평균이 아니라 안정성까지 확인
- `mixture / allocation`: 예산과 비율 배분

---
<!-- footer: "비교 agents" -->

## 19. DoE-guided 운영과 비교한 Agents

| Agent | 운영 방식 | 특징 |
| --- | --- | --- |
| `01 Ratchet` | local ratchet loop | incumbent를 branch head로 두고 좁게 mutation |
| `02 Screening DoE` | simple screening | round마다 한 design question만 분리해 main effect를 읽음 |
| `03 Advanced DoE` | staged DoE program | screening → interaction check → local refinement |

---
<!-- footer: "실험 설정" -->

## 20. 실험 설정

| 항목 | 설정 |
| --- | --- |
| benchmark | `cifar10_real` |
| model | `mlp` |
| agent profiles | `Ratchet`, `Screening DoE`, `Advanced DoE` |
| advisor modes | `plain`, `TPE`, `SMAC`, `TPE+SMAC`, `TPE direct`, `SMAC direct` |
| isolated conditions | `14` |
| execution | root당 validation-history `100` runs + hidden finalize `1`회 |

실행 메모
- 각 condition은 subagent로 별도 root에서 독립 실행
- 최종 검산: finalized manifest `14`, run artifact `100 x 14`
- 이번 비교는 code-edit autoresearch가 아니라 bounded `AutoML + advisory harness` 비교다

탐색 축
- preprocessing: `normalization`, `outlier`, `projection`, `resampling`
- architecture: `hidden_dims`, `activation`, `normalization_layer`
- optimization: `solver`, `learning_rate`, `batch_size`, `max_iter`
- regularization / stability: `weight_decay`, `dropout`, `noise`, `label_smoothing`, `residual_connections`

---
<!-- footer: "결과 요약" -->

## 21. 최종 요약: validation 1등과 hidden 1등은 달랐다

| 관점 | 조건 | Best Val | Hidden Test |
| --- | --- | --- | --- |
| validation 최고 | `screening_plain` | `0.4433` | `0.3700` |
| hidden test 최고 | `ratchet_smac` | `0.4017` | `0.4100` |
| plain 조건 최고 hidden | `ratchet_plain` | `0.4350` | `0.3883` |
| direct 조건 최고 | `tpe_direct` | `0.4383` | `0.3733` |
| dual-advisor 최고 | `screening_tpe_smac` | `0.4200` | `0.3867` |

- `TPE`는 validation ceiling을 자주 올렸지만 hidden winner는 `SMAC` 쪽에서 나왔다.
- 이번 budget `100`에선 `TPE+SMAC` 조합이 단일 advisor를 안정적으로 이기지 못했다.
- 아래 히스토리 plot은 가독성을 위해 `profile별 3개`와 `advisor mode별 3개`로 나눴다.

---
<!-- footer: "Ratchet Variants" -->

## 22. Ratchet 계열 비교

![w:1460](./assets/ratchet_variants_best_and_nonbest.svg)

- `ratchet_tpe`가 validation ceiling `0.4383`으로 가장 높다.
- hidden test는 `ratchet_smac`이 `0.4100`으로 family 최고다.
- `ratchet_tpe_smac`은 점 분산이 크고 best-line도 낮아 coordination cost가 보인다.

---
<!-- footer: "Screening Variants" -->

## 23. Screening 계열 비교

![w:1460](./assets/screening_variants_best_and_nonbest.svg)

- `screening_plain`이 전체 validation 최고 `0.4433`을 만들었다.
- `screening_tpe`는 ceiling이 근접하지만 plain을 넘지는 못했다.
- hidden 쪽에선 `screening_tpe_smac`이 `0.3867`로 family 최고다.

---
<!-- footer: "Advanced Variants" -->

## 24. Advanced 계열 비교

![w:1460](./assets/advanced_variants_best_and_nonbest.svg)

- `advanced_tpe`가 validation ceiling `0.4300`으로 가장 높다.
- hidden은 `advanced_tpe_smac`이 `0.3850`으로 family 최고다.
- Advanced profile은 advisor 도움 없이는 ceiling이 낮고, advisor 의존성이 상대적으로 크다.

---
<!-- footer: "Plain Agents" -->

## 25. Plain agent간 비교

![w:1460](./assets/plain_agents_best_and_nonbest.svg)

- advisor 없이도 `screening_plain`이 validation 1등이다.
- hidden에선 `ratchet_plain`이 `0.3883`으로 plain family 최고다.
- base policy 자체가 이미 다른 탐색 성격을 만든다.

---
<!-- footer: "TPE Agents" -->

## 26. TPE agent간 비교

![w:1460](./assets/tpe_agents_best_and_nonbest.svg)

- `ratchet_tpe`와 `screening_tpe`가 같은 validation ceiling `0.4383`에 도달했다.
- `advanced_tpe`도 좋아졌지만 상위 둘을 뒤집지는 못했다.
- `TPE`는 agent 차이를 줄이며 강한 incumbent 근처로 수렴시키는 경향이 보인다.

---
<!-- footer: "SMAC Agents" -->

## 27. SMAC agent간 비교

![w:1460](./assets/smac_agents_best_and_nonbest.svg)

- validation ceiling은 `screening_smac`이 가장 높다.
- hidden winner는 `ratchet_smac` `0.4100`이다.
- 같은 `SMAC` advice라도 agent policy가 finalize generalization을 크게 바꾼다.

---
<!-- footer: "읽을 점" -->

## 28. 이번 batch에서 읽을 점

- `profile별 3개`는 advisor가 같은 agent 안에서 무엇을 바꾸는지 보여준다.
- `mode별 3개`는 같은 advisor 아래에서 agent policy 차이를 보여준다.
- `dual-advisor`는 per-profile plot에만 남겼다. cross-agent까지 겹치면 비교 이득보다 시각적 잡음이 커진다.
- 핵심 mismatch는 유지된다: validation 최고는 `screening_plain`, hidden 최고는 `ratchet_smac`.

---
<!-- footer: "Harness Lesson" -->

## 29. Harness 관점에서 남는 교훈

- `best val`, `hidden finalize`, `artifact completeness`를 같이 봐야 한다.
- run count와 history row count를 혼동하면 early finalize가 생긴다.
- advisor trace에는 invalid proposal이 섞일 수 있어 log-domain과 search-space guard가 필요하다.
- isolate / finalize / history를 분리해야 mid-run best와 final winner를 동시에 읽을 수 있다.

---
<!-- footer: "한계" -->

## 30. 한계

- 단일 benchmark, single split batch라 분산 추정이 약하다.
- run budget `100`은 dual-advisor의 late gain을 보기엔 짧을 수 있다.
- hidden finalize는 final incumbent `1`회 기준이라 top-k reseeding은 아직 없다.
- code-edit autoresearch loop까지는 포함하지 않았다.

---
<!-- _class: tinytext -->
<!-- footer: "출처" -->

## 31. References

| 구분 | 예시 |
| --- | --- |
| curated landscape | [awesome-autoresearch](https://github.com/alvinreal/awesome-autoresearch), [Awesome Auto Research Tools](https://github.com/handsome-rich/Awesome-Auto-Research-Tools) |
| end-to-end systems | [karpathy/autoresearch](https://github.com/karpathy/autoresearch), [RD-Agent](https://github.com/microsoft/RD-Agent), [AI-Scientist](https://github.com/SakanaAI/AI-Scientist) |
| deep research | [GPT Researcher](https://github.com/assafelovic/gpt-researcher) |
| evaluation | [MLE-bench](https://github.com/openai/mle-bench), [MLAgentBench](https://github.com/snap-stanford/MLAgentBench), [MLR-Bench](https://github.com/chchenhui/mlrbench) |
| optimization baselines | [Optuna docs](https://optuna.readthedocs.io/en/stable/reference/samplers/index.html), [SMAC3 docs](https://automl.github.io/SMAC3/main/) |
| visuals | [AutoML image](https://miro.medium.com/v2/resize:fit:1382/1*ip8VpZ4_KJP8R5EwJ3zRgw.jpeg), [NAS image](https://i.ytimg.com/vi/_dR8a5ZcBgM/sddefault.jpg), [Kubeflow model registry lifecycle image](https://www.kubeflow.org/docs/components/model-registry/images/ml-lifecycle-kubeflow-modelregistry.drawio.svg) |
