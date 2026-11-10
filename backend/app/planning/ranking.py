"""Rank ranges from non-overlapping metric bounds; no weighted composite score."""
from .models import RankRange

HIGHER_IS_BETTER = {"total_sun_hours", "longest_joint_hours"}


def rank_candidates(candidates, metric: str) -> list[RankRange]:
    known = [c for c in candidates if c.decision != "INDETERMINATE" and c.metrics]
    higher = metric in HIGHER_IS_BETTER

    def beats(a, b):
        alo, ahi = a.metrics[metric]
        blo, bhi = b.metrics[metric]
        return alo > bhi+1e-9 if higher else ahi < blo-1e-9

    return [RankRange(
        candidate_id=c.candidate_id,
        rank_min=1+sum(beats(other, c) for other in known if other is not c),
        rank_max=len(known)-sum(beats(c, other) for other in known if other is not c),
        tied_with=[other.candidate_id for other in known if other is not c and not beats(c, other) and not beats(other, c)],
    ) for c in known]


def display_key(candidate, metric, current_site_id=None):
    low, high = candidate.metrics[metric]
    conservative = -low if metric in HIGHER_IS_BETTER else high
    return conservative, candidate.site_id != current_site_id, candidate.start_utc or "", candidate.site_id
