from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from autoresearch.agent_report import ensure_report_file
from autoresearch.agent_profiles import materialize_program
from autoresearch.advisors import (
    ADVISOR_FACTORIES,
    AdvisorError,
    HistoryObservation,
    _json_safe,
    write_snapshot,
)
from autoresearch.artifacts import (
    load_public_artifacts,
    select_best_validation_rows,
    write_finalized_artifact,
    write_public_artifact,
)
from autoresearch.backends import make_backend
from autoresearch.catalog import Catalog, load_catalog
from autoresearch.domain import AdviceSession, CandidateConfig, CandidateResult, RunReport, Submission
from autoresearch.history import append_history
from autoresearch.leaderboard import write_final_report, write_leaderboard
from autoresearch.policy import load_policy
from autoresearch.runtime_paths import (
    advice_current_session_path,
    advice_latest_summary_path,
    advice_session_snapshot_path,
    advice_used_session_path,
    finalized_artifact_path,
    public_artifact_path,
)
from autoresearch.search_space import load_search_space
from autoresearch.submission import load_submission, write_submission
from autoresearch.validation import SubmissionValidationError, validate_submission


class ExperimentRunner:
    def __init__(self, root: Path, catalog: Catalog | None = None) -> None:
        self.root = Path(root)
        self.catalog = catalog or load_catalog(self.root / "experiments" / "benchmark_catalog.toml")

    def _make_run_id(self, agent_name: str, benchmark_id: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{timestamp}-{agent_name}-{benchmark_id}"

    @staticmethod
    def _candidate_signature(candidate: CandidateConfig) -> str:
        return json.dumps(
            _json_safe(
                {
                    "model_family": candidate.model_family,
                    "preprocessing": candidate.preprocessing,
                    "resampling": candidate.resampling,
                    "model": candidate.model,
                }
            ),
            sort_keys=True,
        )

    @staticmethod
    def _result_signature(result: dict[str, object]) -> str:
        return json.dumps(
            _json_safe(
                {
                    "model_family": result.get("model_family", ""),
                    "preprocessing": result.get("preprocessing", {}),
                    "resampling": result.get("resampling", {}),
                    "model": result.get("model", {}),
                }
            ),
            sort_keys=True,
        )

    def _load_seen_candidate_signatures(self, agent_name: str, benchmark_id: str) -> dict[str, dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for artifact in load_public_artifacts(self.root):
            if artifact["agent_name"] != agent_name:
                continue
            for result in artifact["results"]:
                result_benchmark = str(result.get("benchmark_id", artifact["benchmark_id"]))
                if result_benchmark != benchmark_id:
                    continue
                signature = self._result_signature(result)
                seen.setdefault(
                    signature,
                    {
                        "candidate_name": str(result.get("candidate_name", "")),
                        "run_id": str(artifact.get("run_id", "")),
                    },
                )
        return seen

    def _validated_candidate_signature(
        self,
        benchmark_id: str,
        backend: str,
        candidate: CandidateConfig,
    ) -> str:
        normalized_candidate = CandidateConfig(
            name=candidate.name,
            model_family=candidate.model_family,
            preprocessing=_json_safe(candidate.preprocessing),
            resampling=_json_safe(candidate.resampling),
            model=_json_safe(candidate.model),
        )
        submission = Submission(
            benchmark_id=benchmark_id,
            backend=backend,
            candidates=(normalized_candidate,),
            source_path=Path("<generated>"),
        )
        validated = validate_submission(submission, self.catalog)
        return self._candidate_signature(validated.candidates[0])

    def _load_history_observations(
        self,
        agent_name: str,
        benchmark_id: str,
        model_family: str,
    ) -> list[HistoryObservation]:
        observations: list[HistoryObservation] = []
        artifacts = [
            artifact
            for artifact in load_public_artifacts(self.root)
            if artifact["agent_name"] == agent_name
        ]
        for artifact in artifacts:
            for result in artifact["results"]:
                if result.get("benchmark_id", artifact["benchmark_id"]) != benchmark_id:
                    continue
                if result["model_family"] != model_family:
                    continue
                observations.append(
                    HistoryObservation(
                        run_id=artifact["run_id"],
                        candidate=CandidateConfig(
                            name=result["candidate_name"],
                            model_family=result["model_family"],
                            preprocessing=dict(result.get("preprocessing", {})),
                            resampling=dict(result.get("resampling", {})),
                            model=dict(result.get("model", {})),
                        ),
                        validation_score=float(result["validation_score"]),
                    )
                )
        observations.sort(key=lambda item: item.run_id)
        return observations

    def _render_advice_summary(self, agent_name: str, snapshots: list[tuple[object, Path]]) -> str:
        lines = [
            f"# Advice for `{agent_name}`",
            "",
            "Latest advisor snapshots for this condition.",
            "",
        ]
        for snapshot, path in snapshots:
            lines.append(f"## {snapshot.advisor_name}")
            lines.append("")
            lines.append(f"- Snapshot: `{path.name}`")
            lines.append(f"- Search Space: `{snapshot.search_space_id}`")
            lines.append(f"- Prior Runs Seen: `{len(snapshot.history_run_ids)}`")
            lines.append("")
            for recommendation in snapshot.recommendations:
                lines.append(
                    f"- Rank {recommendation.rank}: `{recommendation.candidate.name}` "
                    f"norm={recommendation.candidate.preprocessing.get('normalization', 'none')} "
                    f"resample={recommendation.candidate.resampling.get('strategy', 'none')} "
                    f"model={recommendation.candidate.model}"
                )
                if recommendation.rationale:
                    lines.append(f"  rationale: {recommendation.rationale}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _combine_recommendations(
        self,
        snapshots: list[tuple[object, Path]],
        proposal_count: int,
        excluded_signatures: set[str] | None = None,
        benchmark_id: str | None = None,
        backend: str | None = None,
    ) -> tuple[CandidateConfig, ...]:
        combined: list[CandidateConfig] = []
        seen_signatures: set[str] = set(excluded_signatures or ())
        recommendation_lists = [list(snapshot.recommendations) for snapshot, _ in snapshots]
        index = 0
        while len(combined) < proposal_count and recommendation_lists:
            next_round: list[list[object]] = []
            for recommendations in recommendation_lists:
                if index >= len(recommendations):
                    continue
                candidate = recommendations[index].candidate
                if benchmark_id is not None and backend is not None:
                    signature = self._validated_candidate_signature(benchmark_id, backend, candidate)
                else:
                    signature = self._candidate_signature(candidate)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    combined.append(candidate)
                    if len(combined) >= proposal_count:
                        break
                next_round.append(recommendations)
            recommendation_lists = next_round
            index += 1
        return tuple(combined)

    def _sync_managed_program(self, agent_dir: Path, policy) -> None:
        if policy.mode != "agent":
            return
        if policy.source_path is None or not policy.source_path.exists():
            return
        materialize_program(agent_dir, policy.agent_profile)

    def advise_agent(self, agent_dir: Path) -> AdviceSession:
        agent_dir = Path(agent_dir)
        agent_name = agent_dir.name
        policy = load_policy(self.root, agent_dir)
        self._sync_managed_program(agent_dir, policy)
        summary_path = advice_latest_summary_path(self.root, agent_dir)
        summary_path.parent.mkdir(parents=True, exist_ok=True)

        if not policy.advisors:
            summary_path.write_text(
                f"# Advice for `{agent_name}`\n\nNo advisors configured for this condition.\n",
                encoding="utf-8",
            )
            return AdviceSession(
                agent_name=agent_name,
                policy_mode=policy.mode,
                advisors=policy.advisors,
                snapshot_paths=(),
                summary_path=summary_path,
                wrote_submission=False,
                search_space_id="",
            )

        if policy.search_space_path is None:
            raise ValueError(f"Condition {agent_name!r} defines advisors but no search_space.")

        search_space = load_search_space(policy.search_space_path)
        benchmark = self.catalog.benchmark(search_space.benchmark_id)
        if benchmark.backend != search_space.backend:
            raise ValueError(
                f"Search space backend {search_space.backend!r} does not match benchmark backend {benchmark.backend!r}."
            )
        if policy.mode == "direct":
            proposal_count = min(policy.proposal_count, benchmark.max_candidates_per_submission)
        else:
            proposal_count = policy.proposal_count
        history_rows = self._load_history_observations(
            agent_name=agent_name,
            benchmark_id=search_space.benchmark_id,
            model_family=search_space.model_family,
        )
        seen_signatures = self._load_seen_candidate_signatures(
            agent_name=agent_name,
            benchmark_id=search_space.benchmark_id,
        )

        session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        snapshots: list[tuple[object, Path]] = []
        for advisor_name in policy.advisors:
            try:
                snapshot = ADVISOR_FACTORIES[advisor_name](
                    search_space,
                    history_rows,
                    proposal_count,
                    benchmark.random_seed,
                )
            except KeyError as exc:
                raise AdvisorError(f"Unknown advisor {advisor_name!r}.") from exc
            path = advice_session_snapshot_path(self.root, agent_dir, session_id, advisor_name)
            write_snapshot(snapshot, path)
            snapshots.append((snapshot, path))

        summary_path.write_text(self._render_advice_summary(agent_name, snapshots), encoding="utf-8")

        wrote_submission = False
        if policy.mode == "direct":
            combined = self._combine_recommendations(
                snapshots,
                proposal_count=1,
                excluded_signatures=set(seen_signatures),
                benchmark_id=search_space.benchmark_id,
                backend=search_space.backend,
            )
            if not combined:
                raise AdvisorError(
                    f"Advisors for {agent_name!r} produced only previously seen configs on "
                    f"benchmark {search_space.benchmark_id!r}."
                )
            submission = Submission(
                benchmark_id=search_space.benchmark_id,
                backend=search_space.backend,
                candidates=combined,
                source_path=agent_dir / "submission.toml",
            )
            write_submission(agent_dir / "submission.toml", submission)
            wrote_submission = True

        current_session_path = advice_current_session_path(self.root, agent_dir)
        current_session_path.parent.mkdir(parents=True, exist_ok=True)
        current_session_path.write_text(
            json.dumps(
                {
                    "policy_mode": policy.mode,
                    "advisors": list(policy.advisors),
                    "search_space_id": search_space.search_space_id,
                    "snapshot_paths": [
                        path.relative_to(self.root).as_posix()
                        for _, path in snapshots
                    ],
                    "selection_origin": "advisor_direct" if policy.mode == "direct" else "agent_submission",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return AdviceSession(
            agent_name=agent_name,
            policy_mode=policy.mode,
            advisors=policy.advisors,
            snapshot_paths=tuple(path for _, path in snapshots),
            summary_path=summary_path,
            wrote_submission=wrote_submission,
            search_space_id=search_space.search_space_id,
        )

    def run_agent_submission(self, agent_dir: Path) -> RunReport:
        agent_dir = Path(agent_dir)
        agent_name = agent_dir.name
        policy = load_policy(self.root, agent_dir)
        self._sync_managed_program(agent_dir, policy)
        current_session_path = advice_current_session_path(self.root, agent_dir)
        advice_session: dict[str, object] | None = None
        if current_session_path.exists():
            advice_session = json.loads(current_session_path.read_text(encoding="utf-8"))
        elif policy.mode == "direct" and policy.advisors:
            raise ValueError(
                f"Condition {agent_name!r} is in direct mode and requires `python3 -m autoresearch advise --agent-dir {agent_dir}` first."
            )

        submission = load_submission(agent_dir / "submission.toml")
        validated = validate_submission(submission, self.catalog)
        if len(validated.candidates) != 1:
            raise SubmissionValidationError(
                "Exactly one candidate must be submitted per run in this harness."
            )
        seen_signatures = self._load_seen_candidate_signatures(agent_name, validated.benchmark_id)
        candidate_signature = self._candidate_signature(validated.candidates[0])
        if candidate_signature in seen_signatures:
            prior = seen_signatures[candidate_signature]
            raise SubmissionValidationError(
                f"Candidate {validated.candidates[0].name!r} matches previously evaluated config "
                f"{prior['candidate_name']!r} from run {prior['run_id']} for agent {agent_name!r} "
                f"on benchmark {validated.benchmark_id!r}. Submit a novel config."
            )
        backend = make_backend(validated.backend, self.root)
        ensure_report_file(self.root, agent_dir)

        raw_results = [
            backend.evaluate(validated.benchmark, validated.dataset, candidate)
            for candidate in validated.candidates
        ]
        sorted_results = sorted(
            raw_results,
            key=lambda item: item.validation_score,
            reverse=True,
        )

        ranked_results: list[CandidateResult] = []
        for rank, result in enumerate(sorted_results, start=1):
            ranked_results.append(
                CandidateResult(
                    candidate_name=result.candidate_name,
                    model_family=result.model_family,
                    metric=result.metric,
                    validation_score=result.validation_score,
                    test_score=result.test_score,
                    rank=rank,
                    backend_name=result.backend_name,
                    summary=result.summary,
                    preprocessing=result.preprocessing,
                    resampling=result.resampling,
                    model=result.model,
                    benchmark_id=validated.benchmark_id,
                    dataset_id=validated.dataset.dataset_id,
                )
            )

        run_id = self._make_run_id(agent_name, validated.benchmark_id)
        artifact_path = public_artifact_path(self.root, run_id)
        report = RunReport(
            run_id=run_id,
            agent_name=agent_name,
            benchmark_id=validated.benchmark_id,
            dataset_id=validated.dataset.dataset_id,
            backend_name=backend.backend_name,
            artifact_path=artifact_path,
            results=tuple(ranked_results),
            policy_mode=policy.mode,
            advisors=policy.advisors,
            selection_origin=str(advice_session.get("selection_origin", "manual_submission")) if advice_session else "manual_submission",
            advice_snapshot_paths=tuple(str(path) for path in advice_session.get("snapshot_paths", [])) if advice_session else (),
            search_space_id=str(advice_session.get("search_space_id", "")) if advice_session else "",
        )
        write_public_artifact(report)
        append_history(agent_dir, report, self.root)
        write_leaderboard(self.root)
        if advice_session and current_session_path.exists():
            archived = advice_used_session_path(self.root, agent_dir, run_id)
            archived.parent.mkdir(parents=True, exist_ok=True)
            current_session_path.replace(archived)
        return report

    def finalize_agent(self, agent_dir: Path) -> RunReport:
        agent_dir = Path(agent_dir)
        agent_name = agent_dir.name
        policy = load_policy(self.root, agent_dir)
        self._sync_managed_program(agent_dir, policy)
        public_artifacts = [
            artifact for artifact in load_public_artifacts(self.root) if artifact["agent_name"] == agent_name
        ]
        if not public_artifacts:
            raise ValueError(f"No validation runs found for agent {agent_name!r}.")

        selected_rows = select_best_validation_rows(public_artifacts)
        if not selected_rows:
            raise ValueError(f"No candidate rows available to finalize for agent {agent_name!r}.")

        finalized_results: list[CandidateResult] = []
        for row in sorted(
            selected_rows,
            key=lambda item: (item["dataset"], item["model"], item["benchmark"]),
        ):
            source_artifact = next(
                artifact for artifact in public_artifacts if artifact["run_id"] == row["run_id"]
            )
            source_result = next(
                result
                for result in source_artifact["results"]
                if result["candidate_name"] == row["candidate"] and result["model_family"] == row["model"]
            )
            benchmark = self.catalog.benchmark(source_artifact["benchmark_id"])
            dataset = self.catalog.dataset(source_artifact["dataset_id"])
            backend = make_backend(source_artifact["backend_name"], self.root)
            candidate = CandidateConfig(
                name=source_result["candidate_name"],
                model_family=source_result["model_family"],
                preprocessing=dict(source_result.get("preprocessing", {})),
                resampling=dict(source_result.get("resampling", {})),
                model=dict(source_result.get("model", {})),
            )
            evaluated = backend.evaluate(benchmark, dataset, candidate)
            finalized_results.append(
                CandidateResult(
                    candidate_name=evaluated.candidate_name,
                    model_family=evaluated.model_family,
                    metric=evaluated.metric,
                    validation_score=evaluated.validation_score,
                    test_score=evaluated.test_score,
                    rank=evaluated.rank,
                    backend_name=evaluated.backend_name,
                    summary=evaluated.summary,
                    preprocessing=evaluated.preprocessing,
                    resampling=evaluated.resampling,
                    model=evaluated.model,
                    benchmark_id=source_artifact["benchmark_id"],
                    dataset_id=source_artifact["dataset_id"],
                )
            )

        sorted_results = sorted(
            finalized_results,
            key=lambda item: (item.validation_score, item.test_score),
            reverse=True,
        )
        ranked_results: list[CandidateResult] = []
        for rank, result in enumerate(sorted_results, start=1):
            ranked_results.append(
                CandidateResult(
                    candidate_name=result.candidate_name,
                    model_family=result.model_family,
                    metric=result.metric,
                    validation_score=result.validation_score,
                    test_score=result.test_score,
                    rank=rank,
                    backend_name=result.backend_name,
                    summary=result.summary,
                    preprocessing=result.preprocessing,
                    resampling=result.resampling,
                    model=result.model,
                    benchmark_id=result.benchmark_id,
                    dataset_id=result.dataset_id,
                )
            )

        benchmark_ids = {result.benchmark_id for result in ranked_results if result.benchmark_id}
        dataset_ids = {result.dataset_id for result in ranked_results if result.dataset_id}
        backend_names = {result.backend_name for result in ranked_results if result.backend_name}
        benchmark_id = next(iter(benchmark_ids)) if len(benchmark_ids) == 1 else "multiple"
        dataset_id = next(iter(dataset_ids)) if len(dataset_ids) == 1 else "multiple"
        backend_name = next(iter(backend_names)) if len(backend_names) == 1 else "multiple"
        run_id = self._make_run_id(agent_name, f"{benchmark_id}-final")
        artifact_path = finalized_artifact_path(self.root, agent_name)
        final_report = RunReport(
            run_id=run_id,
            agent_name=agent_name,
            benchmark_id=benchmark_id,
            dataset_id=dataset_id,
            backend_name=backend_name,
            artifact_path=artifact_path,
            results=tuple(ranked_results),
            policy_mode=policy.mode,
            advisors=policy.advisors,
            selection_origin="finalized_best_validation",
        )
        write_finalized_artifact(final_report)
        write_final_report(self.root, agent_dir, final_report)
        write_leaderboard(self.root)
        return final_report
