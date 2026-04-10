from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch.agent_profiles import CLI_AGENT_PROFILE_CHOICES
from autoresearch.catalog import load_catalog
from autoresearch.history_report import (
    build_comparison_report,
    resolve_agent_dirs,
    write_comparison_report,
)
from autoresearch.runner import ExperimentRunner
from autoresearch.scaffold import scaffold_agent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="policy-driven autoresearch harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one agent submission.")
    run_parser.add_argument("--agent-dir", required=True, help="Path to an agent directory.")
    run_parser.add_argument(
        "--catalog",
        default="experiments/benchmark_catalog.toml",
        help="Benchmark catalog path.",
    )

    advise_parser = subparsers.add_parser(
        "advise",
        help="Generate advisor snapshots and optionally write direct submissions for one condition.",
    )
    advise_parser.add_argument("--agent-dir", required=True, help="Path to an agent directory.")
    advise_parser.add_argument(
        "--catalog",
        default="experiments/benchmark_catalog.toml",
        help="Benchmark catalog path.",
    )

    finalize_parser = subparsers.add_parser(
        "finalize-agent",
        help="Reveal hidden test results for the best validation candidates of one agent.",
    )
    finalize_parser.add_argument("--agent-dir", required=True, help="Path to an agent directory.")
    finalize_parser.add_argument(
        "--catalog",
        default="experiments/benchmark_catalog.toml",
        help="Benchmark catalog path.",
    )

    list_parser = subparsers.add_parser("list-benchmarks", help="List configured benchmarks.")
    list_parser.add_argument(
        "--catalog",
        default="experiments/benchmark_catalog.toml",
        help="Benchmark catalog path.",
    )

    scaffold_parser = subparsers.add_parser("init-agent", help="Create a new agent scaffold.")
    scaffold_parser.add_argument("--name", required=True, help="Agent directory name.")
    scaffold_parser.add_argument(
        "--strategy",
        default="01",
        choices=list(CLI_AGENT_PROFILE_CHOICES),
        help="Agent profile to seed into program.md. Supports 01/02/03 plus legacy aliases.",
    )

    history_parser = subparsers.add_parser(
        "history-report",
        help="Compare agent history trajectories with agent-authored report judgments for one benchmark/model slice.",
    )
    history_parser.add_argument(
        "--root",
        default=".",
        help="Project root used to resolve agent paths and output paths.",
    )
    history_parser.add_argument(
        "--agents",
        action="append",
        default=[],
        help="Agent directory path. Can be repeated.",
    )
    history_parser.add_argument(
        "--agent-glob",
        action="append",
        default=[],
        help="Glob under agents/ for agent discovery. Can be repeated.",
    )
    history_parser.add_argument(
        "--agents-dir",
        default="agents",
        help="Agent root directory used with --agent-glob.",
    )
    history_parser.add_argument("--benchmark", required=True, help="Benchmark id to keep.")
    history_parser.add_argument("--model", required=True, help="Model family to keep.")
    history_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where index.html and report.json will be written.",
    )
    history_parser.add_argument("--title", help="Optional report title.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path.cwd()

    if args.command == "run":
        catalog_path = root / args.catalog
        catalog = load_catalog(catalog_path)
        runner = ExperimentRunner(root=root, catalog=catalog)
        report = runner.run_agent_submission(root / args.agent_dir)
        print(f"run_id={report.run_id}")
        print(f"agent={report.agent_name}")
        print(f"benchmark={report.benchmark_id}")
        print(f"best_candidate={report.best_result.candidate_name}")
        print(f"validation_score={report.best_result.validation_score:.6f}")
        print(f"artifact={report.artifact_path}")
        return 0

    if args.command == "advise":
        catalog_path = root / args.catalog
        catalog = load_catalog(catalog_path)
        runner = ExperimentRunner(root=root, catalog=catalog)
        session = runner.advise_agent(root / args.agent_dir)
        print(f"agent={session.agent_name}")
        print(f"mode={session.policy_mode}")
        print(f"advisors={','.join(session.advisors) or '-'}")
        print(f"search_space={session.search_space_id or '-'}")
        print(f"snapshots={len(session.snapshot_paths)}")
        print(f"summary={session.summary_path}")
        print(f"wrote_submission={str(session.wrote_submission).lower()}")
        return 0

    if args.command == "finalize-agent":
        catalog_path = root / args.catalog
        catalog = load_catalog(catalog_path)
        runner = ExperimentRunner(root=root, catalog=catalog)
        report = runner.finalize_agent(root / args.agent_dir)
        print(f"run_id={report.run_id}")
        print(f"agent={report.agent_name}")
        print(f"best_candidate={report.best_result.candidate_name}")
        print(f"validation_score={report.best_result.validation_score:.6f}")
        print(f"test_score={report.best_result.test_score:.6f}")
        print(f"artifact={report.artifact_path}")
        return 0

    if args.command == "list-benchmarks":
        catalog = load_catalog(root / args.catalog)
        for benchmark_id, benchmark in sorted(catalog.benchmarks.items()):
            print(
                f"{benchmark_id}\t{benchmark.dataset_id}\t{benchmark.metric}\t"
                f"{benchmark.backend}\tval={benchmark.validation_size}\t"
                f"test={benchmark.test_size}\tmax_candidates={benchmark.max_candidates_per_submission}"
            )
        return 0

    if args.command == "init-agent":
        agent_dir = scaffold_agent(root=root, agent_name=args.name, strategy=args.strategy)
        print(agent_dir)
        return 0

    if args.command == "history-report":
        analysis_root = (root / args.root).resolve() if not Path(args.root).is_absolute() else Path(args.root).resolve()
        agent_dirs = resolve_agent_dirs(
            root=analysis_root,
            agent_paths=list(args.agents),
            agent_globs=list(args.agent_glob),
            agents_dir=args.agents_dir,
        )
        if not agent_dirs:
            parser.error("history-report requires at least one --agents or --agent-glob match.")

        report = build_comparison_report(
            root=analysis_root,
            agent_dirs=agent_dirs,
            benchmark_id=args.benchmark,
            model_family=args.model,
            title=args.title,
        )
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = analysis_root / output_dir
        html_path, json_path = write_comparison_report(report, output_dir)
        print(f"html={html_path}")
        print(f"json={json_path}")
        print(f"agents={len(report.agents)}")
        return 0

    parser.error(f"Unknown command {args.command!r}")
    return 2
