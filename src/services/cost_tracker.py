"""Track API token usage and compute dollar cost across all phases."""

from dataclasses import dataclass, field
from typing import Optional

from ..config import PricingConfig


@dataclass
class CostEntry:
    """Single API call cost record."""

    model_id: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    phase: str  # "plan", "feature", "develop"
    label: str  # e.g., "FEAT-001 turn 3", "spec_enhancement"

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost


class CostTracker:
    """Tracks token usage and cost across all API calls.

    Accumulates CostEntry records and provides aggregation by phase,
    feature, and total.
    """

    def __init__(self, pricing_config: Optional[PricingConfig] = None):
        if pricing_config is None:
            from ..config import pricing_config as default_pricing
            pricing_config = default_pricing
        self.pricing_config = pricing_config
        self.entries: list[CostEntry] = []

    def record(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        phase: str,
        label: str,
    ) -> CostEntry:
        """Record an API call's token usage and compute cost.

        Args:
            model_id: The Bedrock model ID used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            phase: Pipeline phase ("plan", "feature", "develop")
            label: Human-readable label (e.g., "FEAT-001 turn 3")

        Returns:
            The created CostEntry
        """
        input_cost, output_cost = self.pricing_config.calculate_cost(
            model_id, input_tokens, output_tokens
        )
        entry = CostEntry(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            phase=phase,
            label=label,
        )
        self.entries.append(entry)
        return entry

    def get_phase_cost(self, phase: str) -> float:
        """Get total cost for a specific phase."""
        return sum(e.total_cost for e in self.entries if e.phase == phase)

    def get_phase_tokens(self, phase: str) -> tuple[int, int]:
        """Get total (input_tokens, output_tokens) for a phase."""
        input_t = sum(e.input_tokens for e in self.entries if e.phase == phase)
        output_t = sum(e.output_tokens for e in self.entries if e.phase == phase)
        return input_t, output_t

    def get_feature_cost(self, feature_id: str) -> float:
        """Get total cost for a specific feature (matches label prefix)."""
        return sum(
            e.total_cost for e in self.entries if e.label.startswith(feature_id)
        )

    def get_feature_tokens(self, feature_id: str) -> tuple[int, int]:
        """Get total (input_tokens, output_tokens) for a feature."""
        input_t = sum(
            e.input_tokens for e in self.entries if e.label.startswith(feature_id)
        )
        output_t = sum(
            e.output_tokens for e in self.entries if e.label.startswith(feature_id)
        )
        return input_t, output_t

    @property
    def total_input_tokens(self) -> int:
        return sum(e.input_tokens for e in self.entries)

    @property
    def total_output_tokens(self) -> int:
        return sum(e.output_tokens for e in self.entries)

    @property
    def total_cost(self) -> float:
        return sum(e.total_cost for e in self.entries)

    def get_phase_costs(self) -> dict[str, float]:
        """Get cost breakdown by phase."""
        phases: dict[str, float] = {}
        for entry in self.entries:
            phases[entry.phase] = phases.get(entry.phase, 0.0) + entry.total_cost
        return phases

    def get_feature_costs(self) -> dict[str, float]:
        """Get cost breakdown by feature (for develop phase entries)."""
        features: dict[str, float] = {}
        for entry in self.entries:
            if entry.phase == "develop":
                # Extract feature ID from label (e.g., "FEAT-001 turn 3" -> "FEAT-001")
                feature_id = entry.label.split(" ")[0] if " " in entry.label else entry.label
                features[feature_id] = features.get(feature_id, 0.0) + entry.total_cost
        return features

    def get_summary(self) -> dict:
        """Get full cost summary for state persistence.

        Returns:
            Dict matching CostTracking model structure
        """
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": round(self.total_cost, 6),
            "phase_costs": {k: round(v, 6) for k, v in self.get_phase_costs().items()},
            "feature_costs": {k: round(v, 6) for k, v in self.get_feature_costs().items()},
            "records": [
                {
                    "model_id": e.model_id,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "input_cost": round(e.input_cost, 6),
                    "output_cost": round(e.output_cost, 6),
                    "phase": e.phase,
                    "label": e.label,
                }
                for e in self.entries
            ],
        }

    def restore_from_state(self, cost_tracking_data: dict) -> None:
        """Restore tracker state from persisted data (for --resume).

        Args:
            cost_tracking_data: Dict from CostTracking model
        """
        for record in cost_tracking_data.get("records", []):
            entry = CostEntry(
                model_id=record["model_id"],
                input_tokens=record["input_tokens"],
                output_tokens=record["output_tokens"],
                input_cost=record["input_cost"],
                output_cost=record["output_cost"],
                phase=record["phase"],
                label=record["label"],
            )
            self.entries.append(entry)

    @staticmethod
    def format_cost(cost: float) -> str:
        """Format a cost value for display."""
        if cost < 0.01:
            return f"${cost:.4f}"
        return f"${cost:.2f}"

    def print_turn_summary(self, entry: CostEntry, turn_number: int) -> None:
        """Print a single turn's cost to console."""
        cost_str = self.format_cost(entry.total_cost)
        print(
            f"      💰 Turn {turn_number}: "
            f"{entry.input_tokens:,} in / {entry.output_tokens:,} out = {cost_str}"
        )

    def print_session_summary(self, feature_id: str) -> None:
        """Print cost summary for a feature session."""
        cost = self.get_feature_cost(feature_id)
        input_t, output_t = self.get_feature_tokens(feature_id)
        print(f"   Input tokens: {input_t:,}")
        print(f"   Output tokens: {output_t:,}")
        print(f"   Session cost: {self.format_cost(cost)}")

    def print_total_summary(self) -> None:
        """Print full cost breakdown to console."""
        phase_costs = self.get_phase_costs()
        feature_costs = self.get_feature_costs()

        print(f"\n{'─'*60}")
        print("💰 COST BREAKDOWN")
        print(f"{'─'*60}")

        for phase, cost in sorted(phase_costs.items()):
            input_t, output_t = self.get_phase_tokens(phase)
            print(
                f"   {phase.capitalize()} phase: {self.format_cost(cost):>10}  "
                f"({input_t:,} in / {output_t:,} out)"
            )

        print(f"   {'─'*50}")
        print(
            f"   TOTAL: {self.format_cost(self.total_cost):>16}  "
            f"({self.total_input_tokens:,} in / {self.total_output_tokens:,} out)"
        )

        if feature_costs:
            print(f"\n   Per-feature breakdown:")
            for feature_id, cost in sorted(feature_costs.items()):
                print(f"     {feature_id}: {self.format_cost(cost)}")

        print(f"{'─'*60}")
