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
<!-- footer: "두 질문" -->

## 10. 두 질문

- 성능: `Autoresearch`는 AutoML baseline보다 낫나
- 운영: 어떤 harness가 agent loop를 낫게 만드나

---
<!-- footer: "질문 1" -->

## 11. 질문 1

- 비교 대상: `Autoresearch`, `Optuna TPE`, `SMAC3`
- 비교 조건: 같은 search space, benchmark, budget

---
<!-- footer: "Optuna TPE" -->

## 12. Optuna TPE

- 방법: `good` vs `rest` density 비교
- 의미: 강한 exploitation baseline

---
<!-- footer: "SMAC3" -->

## 13. SMAC3

- 방법: surrogate + racing
- 의미: mixed search space baseline

---
<!-- footer: "결과 TBD" -->

## 14. 결과 TBD

**TBD**

- 실험 진행 중
- 동일 조건 결과 표 추가 예정

---
<!-- footer: "질문 2" -->

## 15. 질문 2

- 초점: 성능이 아니라 운영
- 목표: 즉흥 loop를 실험 체계로 바꾸기

---
<!-- footer: "왜 Harness" -->

## 16. 왜 Harness

- 없으면: attribution 약화, 단계 혼합
- 결과: 잘 정리된 random search로 퇴화

---
<!-- footer: "DoE Harness" -->

## 17. DoE Harness

- 순서: `screening → interaction → refinement`
- 장점: effect attribution, 다음 라운드 설계

---
<!-- footer: "세 프로파일" -->

## 18. 세 프로파일

| Profile | 역할 |
| --- | --- |
| `Ratchet` | incumbent 근처 exploit |
| `Screening` | main effect 분리 |
| `Advanced` | interaction / refinement |

---
<!-- footer: "결과 요약" -->

## 19. 실험 설정

| 항목 | 설정 |
| --- | --- |
| benchmark | `cifar10_real` |
| model | `mlp` |
| conditions | `14` |
| budget | condition당 `100 + finalize 1` |

---
<!-- footer: "탐색 축" -->

## 20. 탐색 축

| 그룹 | 변수 |
| --- | --- |
| preprocessing | `normalization`, `projection`, `resampling` |
| architecture | `hidden_dims`, `activation`, `norm layer` |
| optimization | `solver`, `lr`, `batch` |
| regularization | `wd`, `dropout`, `noise` |

---
<!-- footer: "실험 설정" -->

## 21. 결과 요약

| 관점 | 조건 | 점수 |
| --- | --- | --- |
| best val | `screening_plain` | `0.4433` |
| best hidden | `ratchet_smac` | `0.4100` |
| best direct hidden | `tpe_direct` | `0.3733` |

- 핵심: validation winner와 finalize winner가 다르다.
- 함의: harness가 peak와 generalization을 다르게 만든다.

---
<!-- footer: "Ratchet" -->

## 22. Ratchet

![w:1460](./assets/ratchet_variants_best_and_nonbest.svg)

- 패턴: `TPE`가 ceiling, `SMAC`이 finalize winner.
- 함의: ratchet은 빠른 exploit엔 강하지만 최종 일반화는 advisor choice에 민감하다.

---
<!-- footer: "Screening" -->

## 23. Screening

![w:1460](./assets/screening_variants_best_and_nonbest.svg)

- 패턴: `plain`이 best val, `TPE+SMAC`이 best hidden.
- 함의: screening policy 자체가 강하고, dual advisor 이득은 late-stage에 제한된다.

---
<!-- footer: "Advanced" -->

## 24. Advanced

![w:1460](./assets/advanced_variants_best_and_nonbest.svg)

- 패턴: advisor가 붙을 때만 상위권에 오른다.
- 함의: 복잡한 design은 짧은 budget에서 proposal quality 의존성이 크다.

---
<!-- footer: "Plain" -->

## 25. Plain

![w:1460](./assets/plain_agents_best_and_nonbest.svg)

- 패턴: advisor 없이도 profile 간 gap이 크다.
- 함의: harness choice가 baseline behavior를 먼저 결정한다.

---
<!-- footer: "TPE" -->

## 26. TPE

![w:1460](./assets/tpe_agents_best_and_nonbest.svg)

- 패턴: `ratchet`과 `screening` ceiling이 수렴한다.
- 함의: `TPE`는 profile 차이를 줄이고 incumbent 근처 수렴을 강화한다.

---
<!-- footer: "SMAC" -->

## 27. SMAC

![w:1460](./assets/smac_agents_best_and_nonbest.svg)

- 패턴: best val은 `screening`, best hidden은 `ratchet`.
- 함의: 같은 advisor라도 harness가 selection pressure를 바꾼다.

---
<!-- footer: "핵심 함의" -->

## 28. 핵심 함의

- harness effect는 advisor effect만큼 크다.
- validation 최적화와 finalize 최적화는 다른 문제다.

---
<!-- footer: "운영 교훈" -->

## 29. 운영 교훈

- 지표: `best val`만 보지 말고 `finalize`, `artifact completeness`를 같이 봐야 한다.
- 설계: `isolate / history / finalize` 분리가 있어야 중간 최고와 최종 승자를 함께 읽는다.

---
<!-- footer: "한계" -->

## 30. 한계

- 단일 benchmark, single split
- budget `100`, top-k reseeding 없음
- code-edit autoresearch는 아직 제외

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
