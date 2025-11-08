from __future__ import annotations

from typing import Iterable, List

import pandas as pd

from .data_models import CandidateRecord


def sort_candidates(candidates: Iterable[CandidateRecord]) -> List[CandidateRecord]:
    def sort_key(record: CandidateRecord) -> tuple:
        meta = record.score.metadata
        must_have = float(meta.get("must_have_coverage", 0))
        domain_match = float(meta.get("domain_match", 0))
        trajectory = float(meta.get("positions_count", 0))
        achievements = float(meta.get("achievements_count", 0))
        # Negative for descending order
        return (
            -record.score.final_score,
            -must_have,
            -domain_match,
            -trajectory,
            -achievements,
            record.created_at,
        )

    return sorted(list(candidates), key=sort_key)


def candidates_to_dataframe(candidates: Iterable[CandidateRecord]) -> pd.DataFrame:
    rows = []
    for record in candidates:
        rows.append(
            {
                "Candidate": record.resume.candidate_name,
                "Status": record.status,
                "Fit Score": record.score.fit_score,
                "Excellence Score": record.score.excellence_score,
                "Final Score": record.score.final_score,
                "Must-have Coverage": float(record.score.metadata.get("must_have_coverage", 0.0)),
                "Domain Match": float(record.score.metadata.get("domain_match", 0.0)),
                "Achievements": int(float(record.score.metadata.get("achievements_count", 0.0))),
                "Positions": int(float(record.score.metadata.get("positions_count", 0.0))),
                "Flags": "; ".join(record.score.breakdown.flags),
                "Candidate ID": record.candidate_id,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["Final Score"], ascending=False).reset_index(drop=True)
    return df

