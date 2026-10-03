"""Assessment layer: requirement checks, IC metrics, architecture-preference flags and RFP / compliance
classifications applied to raw physics closures (owner decision A9.22 items 6-7); design-layer gates live in
`design_gates` (A9.22 items 2 and 5)."""
from .closure_checks import (ASSESSMENT_SCHEMA_VERSION, RAW_SCHEMA_VERSION, REQUIREMENT_POINTERS, RAW_ONLY_KEYS,
                             FORBIDDEN_RAW_PREFIXES, FORBIDDEN_RAW_KEYS, Constraints, AssessmentPriors,
                             constraints_from_config, priors_from_config, ic_metrics, assess, legacy_merge,
                             assessment_columns)

__all__ = ["ASSESSMENT_SCHEMA_VERSION", "RAW_SCHEMA_VERSION", "REQUIREMENT_POINTERS", "RAW_ONLY_KEYS",
           "FORBIDDEN_RAW_PREFIXES", "FORBIDDEN_RAW_KEYS", "Constraints", "AssessmentPriors", "constraints_from_config",
           "priors_from_config", "ic_metrics", "assess", "legacy_merge", "assessment_columns"]
