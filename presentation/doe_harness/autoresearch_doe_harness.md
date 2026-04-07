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

26.4.7

서민교

---
<!-- footer: "AutoML 시작" -->

## 1. AutoML이란 무엇인가?

- 모델 개발 탐색 일부 자동화
- 대표 대상: `model selection`, `hyperparameter tuning`, `pipeline search`
- 핵심: 비교적 주어진 `search space` 안 최적 설정 탐색

![w:950](./assets/automl_intro.jpeg)

[출처 이미지](https://miro.medium.com/v2/resize:fit:1382/1*ip8VpZ4_KJP8R5EwJ3zRgw.jpeg)

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

![w:1040](./assets/mlops_kubeflow.svg)

- Autoresearch loop는 이 큰 ML lifecycle 안의 일부
- 실제 시스템: `data`, `experiment`, `model registry`, `deployment`, `monitoring`
- 핵심 역할: `지속 운영`, `추적`, `승격`, `유지관리`

[출처 이미지](https://www.kubeflow.org/docs/components/model-registry/images/ml-lifecycle-kubeflow-modelregistry.drawio.svg)

---
<!-- footer: "부족한 점" -->

## 10. Autoresearch의 단점

- 실험이 즉흥적으로 이어지기 쉬움
- 왜 이 실험을 했는지 attribution이 약함
- 큰 수정, 작은 튜닝, 검증 실험이 섞이기 쉬움
- robustness, replication, interaction 확인이 뒤로 밀림
- 잘 정리된 random search로 퇴화할 위험

---
<!-- footer: "필요한 harness" -->

## 11. 어떤 Harness가 필요한가

- 무엇을 먼저 볼지 정하는 우선순위
- 어떤 조합을 함께 볼지 정하는 규율
- 탐색 단계와 검증 단계 분리
- 작은 수정과 큰 수정을 다르게 다루는 운영 규칙
- 실패도 정보로 남기는 구조
- 다음 라운드를 설계하는 순차 실험 체계

---
<!-- footer: "DoE 개념" -->

## 12. Design of Experiments(DoE)란 무엇인가

- 여러 요인을 한 번에 바꿔 보며 effect를 읽는 실험 설계
- 한 번의 최고점보다 `요인`, `상호작용`, `안정성` 파악에 강점
- 핵심 질문: 무엇을 바꿨고, 무엇이 실제로 영향을 줬는가

![h:330](./assets/doe_cake.png)

[출처 이미지](https://i0.wp.com/michelbaudin.com/wp-content/uploads/2020/10/AstakhovVisualizationOfDOEOnCake.png?resize=691%2C406&ssl=1)

---
<!-- footer: "빌려오는 DoE 개념" -->

## 13. DoE에서 빌려오는 개념

- `screening`: 중요한 요인부터 좁히기
- `factorial thinking`: interaction 보기
- `sequential design`: 라운드별 정교화
- `robust design`: 평균이 아니라 안정성까지 확인
- `mixture / allocation`: 예산과 비율 배분

---
<!-- footer: "비교 agents" -->

## 14. DoE-guided 운영과 비교한 Agents

| 운영 방식 | 특징 |
| --- | --- |
| Vanilla autoresearch | `edit → run → score` 반복, 실험 성격 혼재 |
| DoE-guided autoresearch | factor 정의, 단계 분리, effect / interaction 축적 |

| Agent | 설명 |
| --- | --- |
| `01 Sequential` | 최신 기록에 맞춰 작은 변경을 순차 적용 |
| `02 Simple DoE` | factor와 level을 두고 screening 중심 비교 |
| `03 Advanced DoE Tic-Tac-To` | staged DoE + 실험 타입 예산 분배 |

- `Tic`: 둘 이상 모듈 동시 변경
- `Tac`: 한 모듈 교체
- `To`: 같은 구조 안 수치 조정
- 운영 규칙: `Tic:Tac:To = 1:2:4`

---
<!-- footer: "실험 설정" -->

## 15. 실험 설정

| Benchmark | 데이터 / 제약 | 실제 사용 model | 현재 시작점 |
| --- | --- | --- | --- |
| `cifar10_real` | `max_samples=4000` | `mlp` | 세 agent 모두 `mlp_anchor` control에서 시작 |
| `twenty_newsgroups_real` | `max_samples=8000`, `max_features=2000`, `ngram_max=2`, `min_df=2` | `mlp` | 같은 loop로 benchmark만 전환 |

- 실행 방식: agent별 isolated root를 따로 만들어 context leakage 없이 독립 실행
- 이번 결과: 각 agent가 같은 start control에서 출발해 validation-only `200` runs를 누적

---
<!-- footer: "결과 테이블" -->

## 16. 결과: 성능, 효율, 안정성

조건: `cifar10_real` / `mlp` / curated `10` knobs / validation only

| Agent | Best Val | Run of Best | Gain vs Run 1 | Mean Best-so-Far | Incumbent Updates |
| --- | --- | --- | --- | --- | --- |
| `01 Sequential` | `0.4333` | `37` | `+0.0750` | `0.4282` | `10` |
| `02 Simple DoE` | `0.3850` | `8` | `+0.0133` | `0.3846` | `3` |
| `03 Advanced DoE + Tic-Tac-To` | `0.4033` | `51` | `+0.0450` | `0.4012` | `5` |

---
<!-- footer: "best config" -->

## 17. 결과: 대표 Config

- `01 Sequential`
  `maxabs + svd(32) + [64,32] + relu + adam + batchnorm + wd=0.001 + lr=0.0005 + bs=32`
- `02 Simple DoE`
  `standard + no projection + [64,32] + relu + adam + no internal norm + wd=0.0005 + lr=0.0003 + bs=128`
- `03 Advanced DoE + Tic-Tac-To`
  `maxabs + svd(32) + [64,32] + relu + adam + no internal norm + wd=0.001 + lr=0.0005 + bs=64`

---
<!-- footer: "탐색 궤적" -->

## 18. 결과: 탐색 궤적

![w:1080](./assets/cifar10_curated10_mlp_best_so_far.svg)

- `01 Sequential`: `run 37`에 최고점 도달 후 긴 plateau 유지
- `02 Simple DoE`: `run 8`에 빠르게 best를 찾았지만 ceiling 상승은 약함
- `03 Advanced DoE + Tic-Tac-To`: `run 51`까지 improvement 지속
- 관측된 `Tic:Tac:To = 29:57:114 ≈ 1:1.97:3.93`

---
<!-- footer: "히스토리 해석" -->

## 19. 히스토리에서 읽히는 결론

- `Sequential`은 좁은 surface에서 가장 강했다.
- `Simple DoE`는 early screening은 빨랐지만 ceiling을 많이 못 올렸다.
- `Advanced DoE + Tic-Tac-To`는 중후반 탐색 건강도가 가장 좋았다.
- 작은 factor space에선 strong local refinement가 더 효율적일 수 있다.
- screening-only보다 staged refinement와 budget allocation이 더 중요했다.

---
<!-- footer: "지식 추출 1" -->

## 20. 히스토리와 피드백에서 추출한 튜닝 지식

`01 Sequential`
- 강한 basin: `maxabs + svd(32) + [64,32] + relu + adam`
- `batchnorm`, `batch_size=32`, `lr=0.0005`, `wd=0.001` 쪽이 강했다.
- `sgd` 전환은 반복적으로 약했다.

`02 Simple DoE`
- 강한 basin: `standard + no projection + [64,32] + relu + adam + batch_size=128`
- 초반엔 `normalization`, `learning_rate_init`, `batch_size` screening이 효율적이었다.
- 이후 late-stage refinement policy가 따로 필요했다.

---
<!-- footer: "지식 추출 2" -->

## 21. 히스토리와 피드백에서 추출한 튜닝 지식

`03 Advanced DoE + Tic-Tac-To`
- 강한 basin: `maxabs + svd(32) + [64,32] + relu + adam + batch_size=64`
- `lr=0.0005`, `wd=0.001` 근처가 반복적으로 살아남았다.
- `32x32`, `tanh`, `std+pca32` branch는 자주 약했다.
- `screening → interaction → local refinement`와 `Tic:Tac:To ≈ 1:2:4`가 long-horizon search에 유효했다.

메타 지식
- `history.md`와 `feedback.md`는 다음 benchmark에 재사용할 `configuration prior`와 `search policy prior` 원천이다.
- DOE 계열은 `hypothesis / factors / levels / conclusion` 구조가 남아 지식 추출이 쉽다.

---
<!-- footer: "한계" -->

## 22. 한계

- 문헌 조사나 가설 생성 자체를 대체하진 못함
- 완전히 open-ended한 구조 탐색은 factorization이 어려움
- classical DoE는 코드 중심 search space에 바로 맞지 않을 수 있음
- large-scale 학습에서는 replication 비용이 큼
- 평가 함수가 빈약하면 DoE도 잘못된 목표를 최적화할 수 있음

---
<!-- _class: tinytext -->
<!-- footer: "출처" -->

## 23. References

| 구분 | 예시 |
| --- | --- |
| curated landscape | [awesome-autoresearch](https://github.com/alvinreal/awesome-autoresearch), [Awesome Auto Research Tools](https://github.com/handsome-rich/Awesome-Auto-Research-Tools) |
| end-to-end systems | [karpathy/autoresearch](https://github.com/karpathy/autoresearch), [RD-Agent](https://github.com/microsoft/RD-Agent), [AI-Scientist](https://github.com/SakanaAI/AI-Scientist) |
| deep research | [GPT Researcher](https://github.com/assafelovic/gpt-researcher) |
| evaluation | [MLE-bench](https://github.com/openai/mle-bench), [MLAgentBench](https://github.com/snap-stanford/MLAgentBench), [MLR-Bench](https://github.com/chchenhui/mlrbench) |
| visuals | [AutoML image](https://miro.medium.com/v2/resize:fit:1382/1*ip8VpZ4_KJP8R5EwJ3zRgw.jpeg), [NAS image](https://i.ytimg.com/vi/_dR8a5ZcBgM/sddefault.jpg), [Kubeflow model registry lifecycle image](https://www.kubeflow.org/docs/components/model-registry/images/ml-lifecycle-kubeflow-modelregistry.drawio.svg) |
