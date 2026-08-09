"""Verify cutover settings, rollback readiness, and optional private-source parity."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class RetirementContract:
    phase: Literal["rollback_ready", "retired"]
    authoritative_source: str
    authoritative_config: str
    required_rollback_paths: tuple[str, ...]
    source_sha256: str
    config_sha256: str

    @classmethod
    def load(cls) -> RetirementContract:
        value = json.loads((HERE / "retirement_contract.json").read_text())
        assert value.pop("authoritative_repo") == "Metta-AI/muster"
        return cls(**value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _semantic_python(path: Path) -> str:
    return ast.dump(ast.parse(path.read_text()), include_attributes=False)


def validate_settings() -> None:
    settings = json.loads((HERE / "ladder_settings.json").read_text())
    assert set(settings) == {"round_interval_minutes", "ladder"}
    assert settings["round_interval_minutes"] == 15
    ladder = settings["ladder"]
    scheduler = ladder["scheduler"]
    ranking = ladder["ranking"]
    assert ladder["enabled"] is False
    assert scheduler == {
        "strategy": "scaling_roster",
        "insufficient_players": "do_not_run",
        "seat_rungs": [2, 4, 8, 16, 32, 64],
        "episodes_per_round": 3,
        "roster_overflow": "partition",
        "overflow_episodes_per_table": 1,
        "variant_rotation_by_seat_count": {
            str(seat_count): ["competition"] for seat_count in (2, 4, 8, 16, 32, 64)
        },
    }
    assert ranking["algorithm"] == "score"
    assert ranking["direction"] == "maximize"
    assert ranking["round_scoring_rule"] == "max"
    assert ranking["standing_aggregation"] == "max"
    assert len(ladder["divisions"]) == 1


def validate_retirement(authoritative_root: Path | None = None) -> None:
    contract = RetirementContract.load()
    paths = [ROOT / relative for relative in contract.required_rollback_paths]
    if contract.phase == "rollback_ready":
        missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
        assert not missing, f"rollback artifacts missing before retirement: {missing}"
        source = ROOT / "coworld_pkg/commissioner/muster_commissioner.py"
        config = ROOT / "muster-commissioner.yaml"
        assert _sha256(source) == contract.source_sha256
        assert _sha256(config) == contract.config_sha256
    else:
        present = [str(path.relative_to(ROOT)) for path in paths if path.exists()]
        assert not present, f"retired rollback artifacts still present: {present}"

    if authoritative_root is not None:
        private_source = authoritative_root / contract.authoritative_source
        private_config = authoritative_root / contract.authoritative_config
        assert _semantic_python(
            ROOT / "coworld_pkg/commissioner/muster_commissioner.py"
        ) == _semantic_python(private_source), (
            "public and private commissioner implementations differ semantically"
        )
        assert (
            ROOT / "muster-commissioner.yaml"
        ).read_text() == private_config.read_text(), (
            "public and private commissioner configs differ"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authoritative-root", type=Path)
    args = parser.parse_args()
    validate_settings()
    validate_retirement(args.authoritative_root)
    print("Muster mirror migration and retirement contract is internally consistent")


if __name__ == "__main__":
    main()
