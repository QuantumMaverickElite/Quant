"""Read-only experiment registry and discovery CLI.

The registry is metadata only.  It never executes a research command.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
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
    supported_modes: tuple[ParameterMode, ...] = ("FIXED",)
    configurable: bool = True
    required: bool = False
    nullable: bool = True
    repeatable: bool = False
    source_kind: str = "UNKNOWN"
    source_path: str | None = None
    source_symbol: str | None = None


@dataclass(frozen=True)
class FixedValue:
    value: Any
    mode: Literal["FIXED"] = "FIXED"


@dataclass(frozen=True)
class ChoiceValue:
    values: tuple[Any, ...]
    mode: Literal["CHOICE"] = "CHOICE"


@dataclass(frozen=True)
class SweepValue:
    start: int | float
    stop: int | float
    step: int | float
    mode: Literal["SWEEP"] = "SWEEP"


@dataclass(frozen=True)
class RandomValue:
    distribution: Literal["uniform", "integer_uniform", "choice"]
    minimum: int | float | None = None
    maximum: int | float | None = None
    choices: tuple[Any, ...] = ()
    mode: Literal["RANDOM"] = "RANDOM"


ConfigValue = FixedValue | ChoiceValue | SweepValue | RandomValue


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    parameters: dict[str, ConfigValue]
    name: str | None = None
    notes: str = ""


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
    supported_modes: tuple[ParameterMode, ...] = ("FIXED",),
    source_kind: str = "CLI_DEFAULT",
    source_path: str | None = None,
    source_symbol: str | None = "parse_args",
) -> ParameterSpec:
    if supported_modes == ("FIXED",) and mode != "FIXED":
        supported_modes = ("CHOICE", mode)
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
        supported_modes=supported_modes,
        source_kind=source_kind,
        source_path=source_path,
        source_symbol=source_symbol,
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
        ComponentSpec("component.intelligence.ml_policy.application", "ML policy application", "Capped and thresholded ML-confidence adjustment.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy/application.py",), ("docs/history/intelligence/market_intelligence_v4_5.md",), ("command.intelligence.ml_policy.application",), "Not allocator authority and not event-learning authority."),
        ComponentSpec("component.intelligence.ml_policy.validation", "ML policy validation", "Candidate evaluation and block-bootstrap summaries.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy/validation.py",), ("docs/history/intelligence/market_intelligence_v4_7.md",), ("command.intelligence.ml_policy.validation",), "Historical v4/v5 research line."),
        ComponentSpec("component.intelligence.ml_policy.sweep", "ML policy strength sweep", "Research sweep over strengths, caps, and thresholds.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy/sweep.py",), ("docs/history/intelligence/market_intelligence_v4_4.md", "docs/history/intelligence/market_intelligence_v4_6.md"), ("command.intelligence.ml_policy.sweep",), "Sweep metadata is descriptive; no execution engine is provided."),
        ComponentSpec("component.intelligence.ml_policy.permutation", "ML policy permutation test", "Within-date permutation null testing for ML-confidence policy lift.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", ("src/backtester/intelligence/ml_policy/permutation.py",), ("docs/history/intelligence/market_intelligence_v4_8.md",), ("command.intelligence.ml_policy.permutation",), "Historical research only."),
        ComponentSpec("signals.mean_reversion.builder", "Mean-reversion signal builder", "Build signals from peer-spread features and confidence thresholds.", "ACTIVE CORE", "ACTIVE CORE", ("src/backtester/signals/mean_reversion.py",), ("docs/large_universe_pipeline.md",), ("command.signals.mean_reversion.builder",), "Reusable signal capability; command defaults are separately recorded."),
        ComponentSpec("research.large_universe.peer_spreads", "Large-universe peer-spread generation", "Matrix-oriented peer search and peer-basket spread generation.", "ACTIVE RESEARCH", "ACTIVE RESEARCH", ("scripts/large_universe_peer_search.py", "scripts/generate_peer_basket_spreads.py"), ("docs/large_universe_pipeline.md",), ("command.pipeline.large_universe.peer_spreads",), "Separate from package-oriented small-universe workflows."),
    )
    pipelines = (
        PipelineSpec("pipeline.intelligence.ml_policy", "Historical ML-policy research", "Compare, validate, sweep, and permutation-test ML policy candidates.", "ACTIVE RESEARCH", "HISTORICAL RESEARCH TOOLING", tuple(c.id for c in components[:4]), tuple(c.id for c in commands[:4]), ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*policy*",), ("docs/history/intelligence/market_intelligence_v4_4.md", "docs/history/intelligence/market_intelligence_v4_7.md", "docs/history/intelligence/market_intelligence_v4_8.md"), "Does not promote ML policy into current allocator authority."),
        PipelineSpec("pipeline.large_universe.mean_reversion", "Large-universe mean-reversion pipeline", "Universe to matrices to peer spreads to mean-reversion signals, with optional context/deformation and downstream stress interfaces.", "ACTIVE RESEARCH", "ACTIVE RESEARCH", ("research.large_universe.peer_spreads", "signals.mean_reversion.builder"), ("command.pipeline.large_universe.build_universe", "command.pipeline.large_universe.peer_spreads", "command.signals.mean_reversion.builder"), ("universe files", "price/returns matrices", "peer maps"), ("outputs/correlation/*.parquet", "outputs/signals/*.parquet", "outputs/rust_inputs/*"), ("docs/large_universe_pipeline.md", "docs/architecture.md"), "H20/H100 cache variants are not assigned authority by this pilot."),
    )
    ml_test = ("tests/test_ml_policy_family.py",)
    ml_common = (
        _p("strength", "Policy strength", "float", 20.0, "Multiplier applied to ML minus baseline confidence.", "intelligence.ml_policy", cli_flag="--strength"),
        _p("max_abs_delta", "Maximum absolute delta", "float", 0.10, "Absolute cap on adjusted confidence delta.", "intelligence.ml_policy", cli_flag="--max-abs-delta", units="confidence"),
        _p("min_abs_delta", "Minimum absolute delta", "float", 0.02, "Threshold below which the delta is zeroed.", "intelligence.ml_policy", cli_flag="--min-abs-delta", units="confidence"),
    )
    experiments = (
        ExperimentSpec("intelligence.ml_policy.application", "Apply ML policy strength", "Apply a controlled ML-confidence policy adjustment to saved predictions/signals.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.application",), ("command.intelligence.ml_policy.application",), ("src/backtester/intelligence/ml_policy/application.py",), ("docs/history/intelligence/market_intelligence_v4_5.md",), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*policy*.parquet",), (_p("strength", "Policy strength", "float", 20.0, "Multiplier applied to ML minus baseline confidence.", "intelligence.ml_policy", cli_flag="--strength"), _p("max_abs_delta", "Maximum absolute delta", "float", 0.05, "Absolute confidence cap.", "intelligence.ml_policy", cli_flag="--max-abs-delta"), _p("min_abs_delta", "Minimum absolute delta", "float", 0.0, "Threshold for retaining delta.", "intelligence.ml_policy", cli_flag="--min-abs-delta")), ("historical", "ml-policy", "allocator-diagnostic"), ("scripts/apply_ml_policy_strength.py",), "Not current event-learning or allocator authority."),
        ExperimentSpec("intelligence.ml_policy.validation", "Validate ML policy candidate", "Evaluate candidate policy outputs across prediction periods with block-bootstrap diagnostics.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.validation",), ("command.intelligence.ml_policy.validation",), ("src/backtester/intelligence/ml_policy/validation.py",), ("docs/history/intelligence/market_intelligence_v4_7.md",), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*validation*",), (_p("iterations", "Bootstrap iterations", "integer", 50000, "Number of bootstrap paths.", "intelligence.ml_policy", cli_flag="--iterations"), _p("block_size", "Bootstrap block size", "integer", 3, "Circular block length.", "intelligence.ml_policy", cli_flag="--block-size")), ("historical", "validation", "bootstrap"), ("scripts/validate_ml_policy_candidate.py",), "Research evidence only."),
        ExperimentSpec("intelligence.ml_policy.sweep", "Sweep ML policy strength", "Evaluate documented ML policy strength, cap, and threshold combinations.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.sweep",), ("command.intelligence.ml_policy.sweep",), ("src/backtester/intelligence/ml_policy/sweep.py",), ("docs/history/intelligence/market_intelligence_v4_4.md", "docs/history/intelligence/market_intelligence_v4_6.md"), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*sweep*",), (_p("strengths", "Strength candidates", "list", [0.5, 1, 2, 3, 5, 10, 15, 20], "Existing sweep candidates.", "intelligence.ml_policy", cli_flag="--strengths", mode="SWEEP"), _p("max_abs_deltas", "Cap candidates", "list", ["none", "0.01", "0.02", "0.05", "0.10"], "Existing cap candidates.", "intelligence.ml_policy", cli_flag="--max-abs-deltas", mode="SWEEP")), ("historical", "sweep", "parameter-study"), ("scripts/sweep_ml_policy_strength.py",), "Registry records demonstrated sweep semantics; it does not run them."),
        ExperimentSpec("intelligence.ml_policy.permutation", "Permutation-test ML policy", "Compare ML-policy lift with within-date shuffled-confidence nulls.", "ACTIVE RESEARCH", "intelligence", "historical_ml_policy", "HISTORICAL RESEARCH TOOLING", "pipeline.intelligence.ml_policy", ("component.intelligence.ml_policy.permutation",), ("command.intelligence.ml_policy.permutation",), ("src/backtester/intelligence/ml_policy/permutation.py",), ("docs/history/intelligence/market_intelligence_v4_8.md",), ml_test, ("outputs/intelligence/training_runs/*.parquet",), ("outputs/intelligence/training_runs/*permutation*",), (_p("permutations", "Permutation count", "integer", 1000, "Number of shuffled null trials.", "intelligence.ml_policy", cli_flag="--permutations"), _p("seed", "Random seed", "integer", 42, "Deterministic permutation seed.", "intelligence.ml_policy", cli_flag="--seed")), ("historical", "permutation", "null-test"), ("scripts/permutation_test_ml_policy.py",), "Null testing only; no production promotion."),
        ExperimentSpec("signals.mean_reversion.peer_spread_baseline", "Peer-spread mean-reversion baseline", "Generate mean-reversion signals from peer-spread features using the documented command defaults.", "ACTIVE CORE", "mean_reversion", "mean_reversion", "ACTIVE CORE", "pipeline.large_universe.mean_reversion", ("signals.mean_reversion.builder",), ("command.signals.mean_reversion.builder",), ("scripts/run_mean_reversion_signals.py", "src/backtester/signals/mean_reversion.py"), ("docs/large_universe_pipeline.md",), (), ("outputs/correlation/peer_spreads.parquet",), ("outputs/signals/mean_reversion_signals.parquet",), (_p("min_abs_z", "Minimum absolute z-score", "float", 1.5, "Minimum peer-spread z-score.", "signals.mean_reversion", cli_flag="--min-abs-z"), _p("min_peer_corr", "Minimum peer correlation", "float", 0.30, "Minimum top-k average peer correlation.", "signals.mean_reversion", cli_flag="--min-peer-corr"), _p("allow_short", "Allow short signals", "boolean", False, "Enable both long and short signals.", "signals.mean_reversion", cli_flag="--allow-short")), ("baseline", "mean-reversion", "peer-spread"), ("scripts/run_mean_reversion_signals.py",), "The command is authoritative for this baseline; no H20/H100 variant is inferred."),
        ExperimentSpec("pipeline.large_universe.deformation_weighted", "Deformation-weighted mean-reversion research", "Apply documented correlation-deformation weights to context-adjusted mean-reversion signals.", "ACTIVE RESEARCH", "mean_reversion", "correlation_deformation", "ACTIVE RESEARCH", "pipeline.large_universe.mean_reversion", ("signals.mean_reversion.builder", "research.large_universe.peer_spreads"), (), ("scripts/apply_deformation_weights_to_mean_reversion_signals.py",), ("docs/research_notes/regime_correlation_deformation.md",), (), ("outputs/signals/mean_reversion_signals_context_adjusted.parquet", "outputs/context/market_context_with_regime_deformation.parquet"), ("outputs/signals/mean_reversion_signals_deformation_weighted.parquet",), (), ("deformation", "mean-reversion", "research"), (), "Parameter authority remains in the script and research notes; no unverified defaults are added here.", True),
    )
    parameter_sources = {
        "intelligence.ml_policy.application": "scripts/apply_ml_policy_strength.py",
        "intelligence.ml_policy.validation": "scripts/validate_ml_policy_candidate.py",
        "intelligence.ml_policy.sweep": "scripts/sweep_ml_policy_strength.py",
        "intelligence.ml_policy.permutation": "scripts/permutation_test_ml_policy.py",
        "signals.mean_reversion.peer_spread_baseline": "scripts/run_mean_reversion_signals.py",
    }
    experiments = tuple(
        replace(
            experiment,
            parameters=tuple(
                replace(parameter, source_path=parameter_sources.get(experiment.id))
                for parameter in experiment.parameters
            ),
        )
        for experiment in experiments
    )
    return Registry(components=components, pipelines=pipelines, experiments=experiments, commands=commands)


def _experiment(registry: Registry, experiment_id: str) -> ExperimentSpec:
    for experiment in registry.experiments:
        if experiment.id == experiment_id:
            return experiment
    raise ValueError(f"Unknown experiment ID: {experiment_id}")


def _parameter_map(experiment: ExperimentSpec) -> dict[str, ParameterSpec]:
    return {parameter.id: parameter for parameter in experiment.parameters}


def default_config(experiment_id: str, registry: Registry | None = None) -> ExperimentConfig:
    registry = registry or build_registry()
    experiment = _experiment(registry, experiment_id)
    values: dict[str, ConfigValue] = {}
    for parameter in experiment.parameters:
        if parameter.type == "list":
            values[parameter.id] = ChoiceValue(tuple(parameter.default or ()))
        else:
            values[parameter.id] = FixedValue(parameter.default)
    config = ExperimentConfig(experiment_id=experiment.id, parameters=values)
    errors = validate_config(config, registry)
    if errors:
        raise ValueError("Invalid default configuration: " + "; ".join(errors))
    return config


def _type_matches(parameter: ParameterSpec, value: Any) -> bool:
    if value is None:
        return parameter.nullable
    if parameter.type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if parameter.type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if parameter.type == "boolean":
        return isinstance(value, bool)
    if parameter.type in {"string", "path", "enum"}:
        return isinstance(value, str)
    if parameter.type == "list":
        return isinstance(value, (list, tuple))
    return False


def _scalar_valid(parameter: ParameterSpec, value: Any) -> str | None:
    if not _type_matches(parameter, value):
        return f"parameter {parameter.id} expects {parameter.type}, got {type(value).__name__}"
    if value is None:
        return None
    if parameter.type == "enum" and parameter.allowed_values and value not in parameter.allowed_values:
        return f"parameter {parameter.id} must be one of {list(parameter.allowed_values)!r}"
    if parameter.minimum is not None and value < parameter.minimum:
        return f"parameter {parameter.id} is below minimum {parameter.minimum}"
    if parameter.maximum is not None and value > parameter.maximum:
        return f"parameter {parameter.id} is above maximum {parameter.maximum}"
    return None


def _validate_config_value(parameter: ParameterSpec, value: ConfigValue) -> list[str]:
    errors: list[str] = []
    mode = value.mode
    if mode not in parameter.supported_modes:
        errors.append(f"parameter {parameter.id} does not support mode {mode}")
        return errors
    if isinstance(value, FixedValue):
        error = _scalar_valid(parameter, value.value)
        if error:
            errors.append(error)
    elif isinstance(value, ChoiceValue):
        if not value.values:
            errors.append(f"choice parameter {parameter.id} cannot be empty")
        if parameter.type == "list":
            if any(item is None for item in value.values):
                errors.append(f"choice parameter {parameter.id} contains null")
        else:
            for item in value.values:
                error = _scalar_valid(parameter, item)
                if error:
                    errors.append(error)
    elif isinstance(value, SweepValue):
        if parameter.type not in {"integer", "float"}:
            errors.append(f"sweep parameter {parameter.id} must be numeric")
        for field_name, item in (("start", value.start), ("stop", value.stop), ("step", value.step)):
            error = _scalar_valid(parameter, item)
            if error:
                errors.append(f"{parameter.id}.{field_name}: {error}")
        if value.step == 0:
            errors.append(f"sweep parameter {parameter.id} has zero step")
        elif value.start < value.stop and value.step < 0:
            errors.append(f"sweep parameter {parameter.id} step must be positive")
        elif value.start > value.stop and value.step > 0:
            errors.append(f"sweep parameter {parameter.id} step must be negative")
    elif isinstance(value, RandomValue):
        if value.distribution not in {"uniform", "integer_uniform", "choice"}:
            errors.append(f"random parameter {parameter.id} has unsupported distribution {value.distribution}")
        if value.distribution == "choice":
            if not value.choices:
                errors.append(f"random choice parameter {parameter.id} cannot be empty")
            for item in value.choices:
                error = _scalar_valid(parameter, item)
                if error:
                    errors.append(error)
        else:
            if value.minimum is None or value.maximum is None:
                errors.append(f"random parameter {parameter.id} requires minimum and maximum")
            elif value.minimum > value.maximum:
                errors.append(f"random parameter {parameter.id} minimum exceeds maximum")
            else:
                for item in (value.minimum, value.maximum):
                    error = _scalar_valid(parameter, item)
                    if error:
                        errors.append(error)
            if value.distribution == "integer_uniform" and parameter.type != "integer":
                errors.append(f"integer_uniform parameter {parameter.id} must be integer")
    return errors


def validate_config(config: ExperimentConfig, registry: Registry | None = None) -> list[str]:
    registry = registry or build_registry()
    try:
        experiment = _experiment(registry, config.experiment_id)
    except ValueError as exc:
        return [str(exc)]
    specs = _parameter_map(experiment)
    errors: list[str] = []
    unknown = sorted(set(config.parameters) - set(specs))
    errors.extend(f"unknown parameter: {config.experiment_id}: {item}" for item in unknown)
    for parameter in experiment.parameters:
        if parameter.required and parameter.id not in config.parameters and parameter.default is None:
            errors.append(f"missing required parameter: {parameter.id}")
    for parameter_id, value in config.parameters.items():
        if parameter_id in specs:
            if not specs[parameter_id].configurable:
                errors.append(f"parameter is not configurable: {parameter_id}")
            errors.extend(_validate_config_value(specs[parameter_id], value))
    return sorted(errors)


def resolve_config(config: ExperimentConfig, registry: Registry | None = None) -> ExperimentConfig:
    registry = registry or build_registry()
    defaults = default_config(config.experiment_id, registry)
    merged = dict(defaults.parameters)
    merged.update(config.parameters)
    resolved = ExperimentConfig(config.experiment_id, merged, config.name, config.notes)
    errors = validate_config(resolved, registry)
    if errors:
        raise ValueError("Invalid configuration: " + "; ".join(errors))
    return resolved


def config_to_dict(config: ExperimentConfig, registry: Registry | None = None) -> dict[str, Any]:
    resolved = resolve_config(config, registry)
    parameters: dict[str, Any] = {}
    for parameter_id in sorted(resolved.parameters):
        parameters[parameter_id] = asdict(resolved.parameters[parameter_id])
    return {"experiment_id": resolved.experiment_id, "name": resolved.name, "notes": resolved.notes, "parameters": parameters}


def config_to_json(config: ExperimentConfig, registry: Registry | None = None) -> str:
    return _json(config_to_dict(config, registry))


def config_from_dict(payload: dict[str, Any], registry: Registry | None = None) -> ExperimentConfig:
    if not isinstance(payload, dict) or not isinstance(payload.get("experiment_id"), str):
        raise ValueError("configuration requires an experiment_id")
    raw_parameters = payload.get("parameters", {})
    if not isinstance(raw_parameters, dict):
        raise ValueError("configuration parameters must be an object")
    values: dict[str, ConfigValue] = {}
    for parameter_id, raw in raw_parameters.items():
        if not isinstance(raw, dict) or raw.get("mode") not in {"FIXED", "CHOICE", "SWEEP", "RANDOM"}:
            raise ValueError(f"invalid configuration value for {parameter_id}")
        mode = raw["mode"]
        if mode == "FIXED":
            values[parameter_id] = FixedValue(raw.get("value"))
        elif mode == "CHOICE":
            values[parameter_id] = ChoiceValue(tuple(raw.get("values", ())))
        elif mode == "SWEEP":
            values[parameter_id] = SweepValue(raw.get("start"), raw.get("stop"), raw.get("step"))
        else:
            values[parameter_id] = RandomValue(raw.get("distribution"), raw.get("minimum"), raw.get("maximum"), tuple(raw.get("choices", ())))
    config = ExperimentConfig(payload["experiment_id"], values, payload.get("name"), payload.get("notes", ""))
    errors = validate_config(config, registry)
    if errors:
        raise ValueError("Invalid configuration: " + "; ".join(errors))
    return resolve_config(config, registry)


def load_config_json(text: str, registry: Registry | None = None) -> ExperimentConfig:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid configuration JSON: {exc}") from exc
    return config_from_dict(payload, registry)


def apply_overrides(config: ExperimentConfig, overrides: list[str], registry: Registry | None = None) -> ExperimentConfig:
    registry = registry or build_registry()
    resolved = resolve_config(config, registry)
    specs = _parameter_map(_experiment(registry, config.experiment_id))
    values = dict(resolved.parameters)
    for override in overrides:
        if "=" not in override:
            raise ValueError(f"override must be NAME=VALUE: {override}")
        parameter_id, raw = override.split("=", 1)
        parameter_id = parameter_id.strip()
        if parameter_id not in specs:
            raise ValueError(f"unknown parameter: {parameter_id}")
        parameter = specs[parameter_id]
        try:
            if parameter.type == "boolean":
                if raw.lower() not in {"true", "false"}:
                    raise ValueError("expected true or false")
                value: Any = raw.lower() == "true"
            elif parameter.type == "integer":
                value = int(raw)
            elif parameter.type == "float":
                value = float(raw)
            elif parameter.type == "list":
                value = json.loads(raw)
            else:
                value = raw
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid value for parameter {parameter_id}: {raw!r}") from exc
        values[parameter_id] = FixedValue(value)
    result = ExperimentConfig(config.experiment_id, values, config.name, config.notes)
    errors = validate_config(result, registry)
    if errors:
        raise ValueError("Invalid override: " + "; ".join(errors))
    return result


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


def _print_config(registry: Registry, experiment_id: str, overrides: list[str], as_json: bool) -> int:
    try:
        config = default_config(experiment_id, registry)
        if overrides:
            config = apply_overrides(config, overrides, registry)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if as_json:
        print(config_to_json(config, registry), end="")
        return 0
    print(experiment_id)
    print("PARAMETER       MODE      VALUE")
    overridden = {item.split("=", 1)[0].strip() for item in overrides if "=" in item}
    for parameter_id in sorted(config.parameters):
        value = config.parameters[parameter_id]
        if isinstance(value, FixedValue):
            display = repr(value.value)
        elif isinstance(value, ChoiceValue):
            display = repr(list(value.values))
        elif isinstance(value, SweepValue):
            display = f"{value.start}..{value.stop} step {value.step}"
        else:
            display = value.distribution
        suffix = "  [override]" if parameter_id in overridden else ""
        print(f"{parameter_id:<15} {value.mode:<9} {display}{suffix}")
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
    config_parser = subparsers.add_parser("config", help="Show validated default configuration without running anything.")
    config_parser.add_argument("experiment_id")
    config_parser.add_argument("--json", action="store_true")
    config_parser.add_argument("--set", dest="overrides", action="append", default=[], metavar="NAME=VALUE")
    args = parser.parse_args(argv)
    registry = build_registry()
    if args.command == "list":
        return _print_list(registry, args.json)
    if args.command == "describe":
        return _print_describe(registry, args.experiment_id, args.json)
    if args.command == "config":
        return _print_config(registry, args.experiment_id, args.overrides, args.json)
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
