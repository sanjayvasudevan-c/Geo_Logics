"""Global seeding for reproducibility.

CLAUDE.md §8: "Global seed set for ``random``, ``numpy``, ``torch``, and CUDA; seed recorded in
every result artifact."
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field

import numpy as np

__all__ = ["SeedReport", "set_global_seed"]

_MAX_SEED = 2**32 - 1


@dataclass(frozen=True)
class SeedReport:
    """Record of what was actually seeded, for the run registry.

    Attributes:
        seed: The seed applied.
        libraries: Names of the libraries successfully seeded.
        deterministic_algorithms: Whether torch was put into deterministic-algorithm mode.
        cuda_available: Whether a CUDA device was visible at seeding time.
    """

    seed: int
    libraries: tuple[str, ...] = field(default_factory=tuple)
    deterministic_algorithms: bool = False
    cuda_available: bool = False


def set_global_seed(seed: int, *, deterministic: bool = True) -> SeedReport:
    """Seed every source of randomness the project uses.

    Seeds :mod:`random`, :mod:`numpy`, ``torch`` (CPU and all CUDA devices), and sets
    ``PYTHONHASHSEED``. When ``deterministic`` is true, torch is additionally asked for
    deterministic algorithms and cuDNN autotuning is disabled.

    Args:
        seed: Seed value. Must be in ``[0, 2**32 - 1]``.
        deterministic: Request deterministic torch kernels. Costs some throughput; correct
            default for a project whose results must be reproducible.

    Returns:
        A :class:`SeedReport` describing what was seeded.

    Raises:
        ValueError: If ``seed`` is outside the permitted range.
    """
    if not 0 <= seed <= _MAX_SEED:
        raise ValueError(f"seed must be in [0, {_MAX_SEED}], got {seed}")

    libraries: list[str] = []

    os.environ["PYTHONHASHSEED"] = str(seed)

    random.seed(seed)
    libraries.append("random")

    np.random.seed(seed)
    libraries.append("numpy")

    cuda_available = False
    deterministic_applied = False

    # torch is a hard dependency, but seeding must not hard-fail in a torch-less environment
    # (for example a CPU-only lint job). Import defensively and record what actually happened
    # rather than silently claiming torch was seeded.
    try:
        import torch
    except ImportError:
        pass
    else:
        torch.manual_seed(seed)
        libraries.append("torch")

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            torch.cuda.manual_seed_all(seed)
            libraries.append("torch.cuda")

        if deterministic:
            torch.use_deterministic_algorithms(True, warn_only=True)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
            deterministic_applied = True

    return SeedReport(
        seed=seed,
        libraries=tuple(libraries),
        deterministic_algorithms=deterministic_applied,
        cuda_available=cuda_available,
    )
