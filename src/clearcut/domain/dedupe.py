"""Collapse findings that name the same asset (docs/plan/sdd.md Section 4.1 step 4).

A brand, prop, or other asset can surface once per scene it appears in. This
module owns what "the same asset" means so no other module retypes the rule.
"""

from clearcut.domain.finding import Category, Finding
from clearcut.domain.script import normalize_text

_AssetIdentity = tuple[Category, str]


def _asset_identity(finding: Finding) -> _AssetIdentity:
    return (finding.category, normalize_text(finding.raw_text))


def dedupe_findings(findings: list[Finding]) -> list[tuple[Finding, tuple[int, ...]]]:
    """One entry per distinct asset, each holding every scene it appeared in.

    Asset identity is `(category, normalized raw_text)`. The surviving
    `Finding` is the first one seen for that asset, unchanged. Entries come
    back in first-appearance order and each scene-number tuple ascends.
    """
    survivors: dict[_AssetIdentity, Finding] = {}
    scene_numbers: dict[_AssetIdentity, list[int]] = {}

    for finding in findings:
        identity = _asset_identity(finding)
        if identity not in survivors:
            survivors[identity] = finding
            scene_numbers[identity] = []
        scene_numbers[identity].append(finding.scene_number)

    return [
        (survivors[identity], tuple(sorted(set(scenes))))
        for identity, scenes in scene_numbers.items()
    ]
