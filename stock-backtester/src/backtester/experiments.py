"""Read-only experiment registry and discovery CLI.

The registry is metadata only.  It never executes a research command.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


ParameterType = Literal["integer", "float", "boolean", "string", "enum", "path", "list"]
ParameterMode = Literal["FIXED", "SWEEP", "CHOICE", "RANDOM"]


@dataclass(frozen=True)
class ParameterSpec:
    id: str
    display_name: str
    type: ParameterType
    default: Any = None
    description: str = ""
    owner: str = ""
    units: str | None = None
    allowed_values: tuple[Any, ...] = ()
    minimum: float | int | None = None
    maximum: float | int | None = None
    cli_flag: str | None = None
    mode: ParameterMode = "FIXED"
    configurable: bool = True


@dataclass(frozen=True)
class CommandSpec:
    id: str
    title: str
    path: str
    invocation: str
    purpose: str
    status: str
    compatibility: bool = True


@dataclass(frozen=True)
class ComponentSpec:
    id: str
    title: str
    purpose: str
    status: str
    authority: str
    implementation_paths: tuple[str, ...] = ()
    documentation_paths: tuple[str, ...] = ()
    command_refs: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class PipelineSpec:
    id: str
    title: str
    purpose: str
    status: str
    authority: str
    component_refs: tuple[str, ...] = ()
    command_refs: tuple[str, ...] = ()
    input_paths: tuple[str, ...] = ()
    output_paths: tuple[str, ...] = ()
    documentation_paths: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class ExperimentSpec:
    id: str
    title: str
    purpose: str
    status: str
    subsystem: str
    research_family: str
    authority: str
    pipeline_ref: str | None = None
    component_refs: tuple[str, ...] = ()
    command_refs: tuple[str, ...] = ()
    implementation_paths: tuple[str, ...] = ()
    documentation_paths: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    input_paths: tuple[str, ...] = ()
    output_paths: tuple[str, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    tags: tuple[str, ...] = ()
    compatibility_commands: tuple[str, ...] = ()
    notes: str = ""
    user_decision_required: bool = False


@dataclass(frozen=True)
class Registry:
    components: tuple[ComponentSpec, ...] = ()
    pipelines: tuple[PipelineSpec, ...] = ()
    experiments: tuple[ExperimentSpec, ...] = ()
    commands: tuple[CommandSpec, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def ids(self) -> set[str]:
        return {
            item.id
            for group in (self.components, self.pipelines, self.experiments, self.commands)
            for item in group
        }


def _p(
    id: str,
    display_name: str,
    type: ParameterType,
    default: Any,
    description: str,
    owner: str,
    *,
    cli_flag: str | None = None,
    units: str | None = None,
    allowed_values: tuple[Any, ...] = (),
    minimum: float | int | None = None,
    maximum: float | int | None = None,
    mode: ParameterMode = "FIXED",
) -> ParameterSpec:
    return ParameterSpec(
        id=id,
        display_name=display_name,
        type=type,
        default=default,
        description=description,
        owner=owner,
        cli_flag=cli_flag,
        units=units,
        allowed_values=allowed_values,
        minimum=minimum,
        maximum=maximum,
        mode=mode,
    )


def build_registry() -> Registry:
    commands = (
        CommandSpec("command.intelligence.ml_policy.application", "Apply ML policy strength", "scripts/apply_ml_policy_strength.py", "python -m scripts.apply_ml_policy_strength", "Apply capped ML-confidence adjustments to a saved signal table.", "ACTIVE RESEARCH"),
        CommandSpec("command.intelligence.ml_policy.validation", "Validate ML policy candidate", "scripts/validate_ml_policy_candidate.py", "python -m scripts.validate_ml_policy_candidate", "Validate candidate policy results with block-bootstrap summaries.", "ACTIVE RESEARCH"),
        CommandSpec("command.intelligence.ml_policy.sweep", "Sweep ML policy strength", "scripts/sweep_ml_policy_strength.py", "python -m scripts.sweep_ml_policy_strength", "Evaluate documented strength and cap combinations.", "ACTIVE RESEARCH"),
        CommandSpec("command.intelligence.ml_policy.permutation", "Permutation-test ML policy", "scripts/permutation_test_ml_policy.py", "python -m scripts.permutation_test_ml_policy", "Compare policy lift against within-date shuffled ML-confidence nulls.", "ACTIVE RESEARCH"),
        CommandSpec("command.signals.mean_reversion.builder", "Build mean-reversion signals", "scripts/run_mean_reversion_signals.py", "python scripts/run_mean_reversion_signals.py", "Generate signals from peer-spread features.", "ACTIVE CORE"),
        CommandSpec("command.pipeline.large_universe.build_universe", "Build research universe", "scripts/build_universe.py", "python scripts/build_universe.py", "Build a filtered large-universe ticker file.", "ACTIVE RESEARCH"),
        CommandSpec("command.pipeline.large_universe.peer_spreads", "Generate peer spreads", "scripts/generate_peer_basket_spreads.py", "python scripts/generate_peer_basket_spreads.py", "Generate peer-basket spread features from matrix research inputs.", "ACTIVE RESEARCH"),
    )
    components = (
        ComponentSpec("component.intelligence.ml_policy.application", "ML policy application", "Capped and thresholded ML-confidence adjustment.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy_application.py",), ("docs/market_intelligence_v4_5.md",), ("command.intelligence.ml_policy.application",), "Not allocator authority and not event-learning authority."),
        ComponentSpec("component.intelligence.ml_policy.validation", "ML policy validation", "Candidate evaluation and block-bootstrap summaries.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy_validation.py",), ("docs/market_intelligence_v4_7.md",), ("command.intelligence.ml_policy.validation",), "Historical v4/v5 research line."),
        ComponentSpec("component.intelligence.ml_policy.sweep", "ML policy strength sweep", "Research sweep over strengths, caps, and thresholds.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy_sweep.py",), ("docs/market_intelligence_v4_4.md", "docs/market_intelligence_v4_6.md"), ("command.intelligence.ml_policy.sweep",), "Sweep metadata is descriptive; no execution engine is provided."),
        ComponentSpec("component.intelligence.ml_policy.permutation", "ML policy permutation test", "Within-date permutation null testing for ML-confidence policy lift.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy_permutation.py",), ("docs/market_intelligence_v4_8.md",), ("command.intelligence.ml_policy.permutation",), "Historical research only."),
        ComponentSpec("signals.mean_reversion.builder", "Mean-reversion signal builder", "Build signals from peer-spread features and confidence thresholds.", "ACTIVE CORE", "ACTIVE CORE", ("src/backtester/signals/mean_reversion.py",), ("docs/large_universe_pipline.md",), ("command.signals.mean_reversion.builder",), "Reusable signal capability; command defaults are separately recorded."),
        ComponentSpec("research.large_universe.peer_spreads", "Large-universe peer-spread generation", "Matrix-oriented peer search and peer-basket spread generation.", "ACTIVE RESEARCH", "ACTIVE RESEARCH", ("scripts/large_universe_peer_search.py", "scripts/generate_peer_basket_spreads.py"), ("docs/large_universe_pipline.md",), ("command.pipeline.large_universe.peer_spreads",), "Separate from package-oriented small-universe workflows."),
    )
    pipelines = (
        PipelineSpec("pipeline.intelligence.ml_policy", "Historical ML-policy research", "Compare, validate, sweep, and permutation-test ML policy candidates.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", tuple(c.id for c in components[:4]), tuple(c.id for c in commands[:4]), ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*policy*",), ("docs/market_intelligence_v4_4.md", "docs/market_intelligence_v4_7.md", "docs/market_intelligence_v4_8.md"), "Does not promote ML policy into current allocator authority."),
        PipelineSpec("pipeline.large_universe.mean_reversion", "Large-universe mean-reversion pipeline", "Universe to matrices to peer spreads to mean-reversion signals, with optional context/deformation and downstream stress interfaces.", "ACTIVE RESEARCH", "ACTIVE RESEARCH", ("research.large_universe.peer_spreads", "signals.mean_reversion.builder"), ("command.pipeline.large_universe.build_universe", "command.pipeline.large_universe.peer_spreads", "command.signals.mean_reversion.builder"), ("universe files", "price/returns matrices", "peer maps"), ("outputs/correlation/*.parquet", "outputs/signals/*.parquet", "outputs/rust_inputs/*"), ("docs/large_universe_pipline.md", "docs/reorg/CURRENT_ARCHITECTURE.md"), "H20/H100 cache variants are not assigned authority by this pilot."),
    )
    ml_test = ("scripts/test_ml_policy_family.py",)
    ml_common = (
        _p("strength", "Policy strength", "float", 20.0, "Multiplier applied to ML minus baseline confidence.", "intelligence.ml_policy", cli_flag="--strength"),
        _p("max_abs_delta", "Maximum absolute delta", "float", 0.10, "Absolute cap on adjusted confidence delta.", "intelligence.ml_policy", cli_flag="--max-abs-delta", units="confidence"),
        _p("min_abs_delta", "Minimum absolute delta", "float", 0.02, "Threshold below which the delta is zeroed.", "intelligence.ml_policy", cli_flag="--min-abs-delta", units="confidence"),
    )
    experiments = (
        ExperimentSpec("intelligence.ml_policy.application", "Apply ML policy strength", "Apply a controlled ML-confidence policy adjustment to saved predictions/signals.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.application",), ("command.intelligence.ml_policy.application",), ("src/backtester/intelligence/ml_policy_application.py",), ("docs/market_intelligence_v4_5.md",), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*policy*.parquet",), (_p("strength", "Policy strength", "float", 20.0, "Multiplier applied to ML minus baseline confidence.", "intelligence.ml_policy", cli_flag="--strength"), _p("max_abs_delta", "Maximum absolute delta", "float", 0.05, "Absolute confidence cap.", "intelligence.ml_policy", cli_flag="--max-abs-delta"), _p("min_abs_delta", "Minimum absolute delta", "float", 0.0, "Threshold for retaining delta.", "intelligence.ml_policy", cli_flag="--min-abs-delta")), ("historical", "ml-policy", "allocator-diagnostic"), ("scripts/apply_ml_policy_strength.py",), "Not current event-learning or allocator authority."),
        ExperimentSpec("intelligence.ml_policy.validation", "Validate ML policy candidate", "Evaluate candidate policy outputs across prediction periods with block-bootstrap diagnostics.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.validation",), ("command.intelligence.ml_policy.validation",), ("src/backtester/intelligence/ml_policy_validation.py",), ("docs/market_intelligence_v4_7.md",), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*validation*",), (_p("iterations", "Bootstrap iterations", "integer", 50000, "Number of bootstrap paths.", "intelligence.ml_policy", cli_flag="--iterations"), _p("block_size", "Bootstrap block size", "integer", 3, "Circular block length.", "intelligence.ml_policy", cli_flag="--block-size")), ("historical", "validation", "bootstrap"), ("scripts/validate_ml_policy_candidate.py",), "Research evidence only."),
        ExperimentSpec("intelligence.ml_policy.sweep", "Sweep ML policy strength", "Evaluate documented ML policy strength, cap, and threshold combinations.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.sweep",), ("command.intelligence.ml_policy.sweep",), ("src/backtester/intelligence/ml_policy_sweep.py",), ("docs/market_intelligence_v4_4.md", "docs/market_intelligence_v4_6.md"), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*sweep*",), (_p("strengths", "Strength candidates", "list", [0.5, 1, 2, 3, 5, 10, 15, 20], "Existing sweep candidates.", "intelligence.ml_policy", cli_flag="--strengths", mode="SWEEP"), _p("max_abs_deltas", "Cap candidates", "list", ["none", "0.01", "0.02", "0.05", "0.10"], "Existing cap candidates.", "intelligence.ml_policy", cli_flag="--max-abs-deltas", mode="SWEEP")), ("historical", "sweep", "parameter-study"), ("scripts/sweep_ml_policy_strength.py",), "Registry records demonstrated sweep semantics; it does not run them."),
        ExperimentSpec("intelligence.ml_policy.permutation", "Permutation-test ML policy", "Compare ML-policy lift with within-date shuffled-confidence nulls.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.permutation",), ("command.intelligence.ml_policy.permutation",), ("src/backtester/intelligence/ml_policy_permutation.py",), ("docs/market_intelligence_v4_8.md",), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*permutation*",), (_p("permutations", "Permutation count", "integer", 1000, "Number of shuffled null trials.", "intelligence.ml_policy", cli_flag="--permutations"), _p("seed", "Random seed", "integer", 42, "Deterministic permutation seed.", "intelligence.ml_policy", cli_flag="--seed")), ("historical", "permutation", "null-test"), ("scripts/permutation_test_ml_policy.py",), "Null testing only; no production promotion."),
        ExperimentSpec("signals.mean_reversion.peer_spread_baseline", "Peer-spread mean-reversion baseline", "Generate mean-reversion signals from peer-spread features using the documented command defaults.", "ACTIVE CORE", "mean_reversion", "mean_reversion", "ACTIVE CORE", "pipeline.large_universe.mean_reversion", ("signals.mean_reversion.builder",), ("command.signals.mean_reversion.builder",), ("scripts/run_mean_reversion_signals.py", "src/backtester/signals/mean_reversion.py"), ("docs/large_universe_pipline.md",), (), ("outputs/correlation/peer_spreads.parquet",), ("outputs/signals/mean_reversion_signals.parquet",), (_p("min_abs_z", "Minimum absolute z-score", "float", 1.5, "Minimum peer-spread z-score.", "signals.mean_reversion", cli_flag="--min-abs-z"), _p("min_peer_corr", "Minimum peer correlation", "float", 0.30, "Minimum top-k average peer correlation.", "signals.mean_reversion", cli_flag="--min-peer-corr"), _p("allow_short", "Allow short signals", "boolean", False, "Enable both long and short signals.", "signals.mean_reversion", cli_flag="--allow-short")), ("baseline", "mean-reversion", "peer-spread"), ("scripts/run_mean_reversion_signals.py",), "The command is authoritative for this baseline; no H20/H100 variant is inferred."),
        ExperimentSpec("pipeline.large_universe.deformation_weighted", "Deformation-weighted mean-reversion research", "Apply documented correlation-deformation weights to context-adjusted mean-reversion signals.", "ACTIVE RESEARCH", "mean_reversion", "correlation_deformation", "ACTIVE RESEARCH", "pipeline.large_universe.mean_reversion", ("signals.mean_reversion.builder", "research.large_universe.peer_spreads"), (), ("scripts/apply_deformation_weights_to_mean_reversion_signals.py",), ("docs/research_notes/regime_correlation_deformation.md",), (), ("outputs/signals/mean_reversion_signals_context_adjusted.parquet", "outputs/context/market_context_with_regime_deformation.parquet"), ("outputs/signals/mean_reversion_signals_deformation_weighted.parquet",), (), ("deformation", "mean-reversion", "research"), (), "Parameter authority remains in the script and research notes; no unverified defaults are added here.", True),
    )
    return Registry(components=components, pipelines=pipelines, experiments=experiments, commands=commands)


def _path_exists(root: Path, path: str) -> bool:
    return (root / path).is_file()


def validate_registry(registry: Registry | None = None, root: Path | None = None) -> list[str]:
    registry = registry or build_registry()
    root = root or Path(__file__).resolve().parents[2]
    errors: list[str] = []
    groups = {"component": registry.components, "pipeline": registry.pipelines, "experiment": registry.experiments, "command": registry.commands}
    all_ids: list[str] = [item.id for group in groups.values() for item in group]
    for item_id in sorted({item for item in all_ids if all_ids.count(item) > 1}):
        errors.append(f"duplicate id: {item_id}")
    ids = set(all_ids)
    for command in registry.commands:
        if not _path_exists(root, command.path):
            errors.append(f"missing command path: {command.id}: {command.path}")
    for component in registry.components:
        for path in component.implementation_paths + component.documentation_paths:
            if not _path_exists(root, path):
                errors.append(f"missing component path: {component.id}: {path}")
        for ref in component.command_refs:
            if ref not in ids:
                errors.append(f"missing command reference: {component.id}: {ref}")
    for pipeline in registry.pipelines:
        for ref in pipeline.component_refs + pipeline.command_refs:
            if ref not in ids:
                errors.append(f"missing pipeline reference: {pipeline.id}: {ref}")
        for path in pipeline.documentation_paths:
            if not _path_exists(root, path):
                errors.append(f"missing pipeline documentation: {pipeline.id}: {path}")
    valid_types = {"integer", "float", "boolean", "string", "enum", "path", "list"}
    valid_modes = {"FIXED", "SWEEP", "CHOICE", "RANDOM"}
    for experiment in registry.experiments:
        if experiment.pipeline_ref and experiment.pipeline_ref not in ids:
            errors.append(f"missing pipeline reference: {experiment.id}: {experiment.pipeline_ref}")
        for ref in experiment.component_refs + experiment.command_refs:
            if ref not in ids:
                errors.append(f"missing experiment reference: {experiment.id}: {ref}")
        for path in experiment.implementation_paths + experiment.documentation_paths + experiment.test_paths:
            if not _path_exists(root, path):
                errors.append(f"missing experiment path: {experiment.id}: {path}")
        for path in experiment.compatibility_commands:
            if not _path_exists(root, path):
                errors.append(f"missing compatibility command: {experiment.id}: {path}")
        for parameter in experiment.parameters:
            if parameter.type not in valid_types:
                errors.append(f"invalid parameter type: {experiment.id}: {parameter.id}")
            if parameter.mode not in valid_modes:
                errors.append(f"invalid parameter mode: {experiment.id}: {parameter.id}")
            if parameter.type == "enum" and not parameter.allowed_values:
                errors.append(f"enum parameter has no allowed values: {experiment.id}: {parameter.id}")
            if parameter.minimum is not None and parameter.maximum is not None and parameter.minimum > parameter.maximum:
                errors.append(f"parameter range is inverted: {experiment.id}: {parameter.id}")
    return sorted(errors)


def _experiment_dict(registry: Registry, experiment: ExperimentSpec) -> dict[str, Any]:
    data = asdict(experiment)
    components = {item.id: item for item in registry.components}
    pipelines = {item.id: item for item in registry.pipelines}
    commands = {item.id: item for item in registry.commands}
    data["components"] = [asdict(components[ref]) for ref in experiment.component_refs if ref in components]
    data["pipeline"] = asdict(pipelines[experiment.pipeline_ref]) if experiment.pipeline_ref in pipelines else None
    data["commands"] = [asdict(commands[ref]) for ref in experiment.command_refs if ref in commands]
    return data


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _print_list(registry: Registry, as_json: bool) -> int:
    experiments = sorted(registry.experiments, key=lambda item: (item.subsystem, item.research_family, item.id))
    if as_json:
        print(_json({"experiments": [asdict(item) for item in experiments]}), end="")
        return 0
    current_group: tuple[str, str] | None = None
    for experiment in experiments:
        group = (experiment.subsystem.upper(), experiment.research_family.upper())
        if group != current_group:
            if current_group is not None:
                print()
            print(f"{group[0]} / {group[1]}")
            current_group = group
        print(f"  {experiment.id}")
        print(f"      {experiment.title} [{experiment.status}]")
    return 0


def _print_describe(registry: Registry, experiment_id: str, as_json: bool) -> int:
    experiment = next((item for item in registry.experiments if item.id == experiment_id), None)
    if experiment is None:
        print(f"Unknown experiment ID: {experiment_id}", file=sys.stderr)
        return 2
    data = _experiment_dict(registry, experiment)
    if as_json:
        print(_json(data), end="")
        return 0
    print(f"{experiment.id}: {experiment.title}")
    print(f"Purpose: {experiment.purpose}")
    print(f"Status: {experiment.status}")
    print(f"Authority: {experiment.authority}")
    print(f"Implementation: {', '.join(experiment.implementation_paths) or 'UNKNOWN'}")
    print(f"Commands: {', '.join(experiment.compatibility_commands) or 'none'}")
    print(f"Inputs: {', '.join(experiment.input_paths) or 'UNKNOWN'}")
    print(f"Outputs: {', '.join(experiment.output_paths) or 'UNKNOWN'}")
    print(f"Documentation: {', '.join(experiment.documentation_paths) or 'none'}")
    print(f"Tests: {', '.join(experiment.test_paths) or 'none'}")
    if experiment.parameters:
        print("Parameters:")
        for parameter in experiment.parameters:
            flag = f", cli={parameter.cli_flag}" if parameter.cli_flag else ""
            print(f"  {parameter.id}: {parameter.type}, default={parameter.default!r}, mode={parameter.mode}{flag}")
    print(f"Notes: {experiment.notes or 'none'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only research experiment registry discovery.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="List registered experiments.")
    list_parser.add_argument("--json", action="store_true")
    describe_parser = subparsers.add_parser("describe", help="Describe one registered experiment.")
    describe_parser.add_argument("experiment_id")
    describe_parser.add_argument("--json", action="store_true")
    validate_parser = subparsers.add_parser("validate", help="Validate registry references and metadata.")
    validate_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    registry = build_registry()
    if args.command == "list":
        return _print_list(registry, args.json)
    if args.command == "describe":
        return _print_describe(registry, args.experiment_id, args.json)
    errors = validate_registry(registry)
    if args.json:
        print(_json({"valid": not errors, "errors": errors}), end="")
    elif errors:
        print("Registry INVALID")
        for error in errors:
            print(f"- {error}")
    else:
        print("Registry valid")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
