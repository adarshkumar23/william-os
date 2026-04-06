"""
WILLIAM OS - Deterministic user bucketing for A/B experiments.
"""

from __future__ import annotations

import hashlib
import uuid


def _stable_hash_bucket(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def assign_variant(
    *,
    user_id: uuid.UUID,
    experiment_key: str,
    variants: list[str],
    seed: str = "william-os",
) -> str:
    if not variants:
        raise ValueError("variants must not be empty")

    bucket = _stable_hash_bucket(f"{seed}:{experiment_key}:{user_id}")
    size = 100 / len(variants)
    index = int(bucket // size)
    if index >= len(variants):
        index = len(variants) - 1
    return variants[index]


def get_assignments(
    *,
    user_id: uuid.UUID,
    experiments: dict[str, list[str]],
    seed: str = "william-os",
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for key, variants in experiments.items():
        assignments[key] = assign_variant(
            user_id=user_id,
            experiment_key=key,
            variants=variants,
            seed=seed,
        )
    return assignments
