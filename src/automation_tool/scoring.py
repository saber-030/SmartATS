from __future__ import annotations

from typing import Dict, List, Tuple

from .data_models import (
    CandidateScore,
    JDFeatures,
    ResumeFeatures,
    ScoreBreakdown,
    ScoreComponent,
    ScoringConfig,
)


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _format_percentage(value: float) -> str:
    return f"{round(value * 100)}%"


def _compute_must_have_component(
    jd: JDFeatures,
    resume: ResumeFeatures,
    weight: float,
) -> Tuple[float, str, float]:
    required = set(skill.lower() for skill in jd.required_skills)
    if not required:
        return weight, "No must-have skills defined; awarding full credit.", 1.0
    candidate_skills = set(skill.lower() for skill in resume.skills)
    matched = required.intersection(candidate_skills)
    coverage = _safe_divide(len(matched), len(required))
    score = coverage * weight
    rationale = (
        f"Matched {len(matched)}/{len(required)} required skills "
        f"({_format_percentage(coverage)} coverage)."
    )
    return score, rationale, coverage


def _compute_experience_component(
    jd: JDFeatures,
    resume: ResumeFeatures,
    weight: float,
) -> Tuple[float, str]:
    required = jd.req_years_overall
    candidate = resume.overall_years_experience
    if not required and not candidate:
        return weight, "No experience data provided; awarding full credit."
    if required and not candidate:
        return 0.3 * weight, "Missing candidate experience data; giving partial credit."
    if not required and candidate:
        return weight, "No required years specified; awarding full credit."

    assert required is not None and candidate is not None
    ratio = min(candidate / required, 1.2)
    score = min(ratio, 1.0) * weight if candidate >= required else ratio * weight
    rationale = (
        f"Candidate has {candidate:.1f} yrs against {required:.1f} yrs required "
        f"({_format_percentage(min(candidate / required, 1.0))} alignment)."
    )
    return score, rationale


def _compute_domain_component(
    jd: JDFeatures,
    resume: ResumeFeatures,
    weight: float,
) -> Tuple[float, str, float]:
    required_domains = set(domain.lower() for domain in jd.domains)
    if not required_domains:
        return weight, "No domain requirements provided; awarding full credit.", 1.0
    candidate_domains = set(domain.lower() for domain in resume.domains)
    matched = required_domains.intersection(candidate_domains)
    match_ratio = _safe_divide(len(matched), len(required_domains))
    score = match_ratio * weight
    rationale = (
        f"Matched {len(matched)}/{len(required_domains)} required domains "
        f"({_format_percentage(match_ratio)} coverage)."
    )
    return score, rationale, match_ratio


def _compute_location_component(
    jd: JDFeatures,
    resume: ResumeFeatures,
    weight: float,
) -> Tuple[float, str]:
    job_location = (jd.location or "").lower()
    candidate_location = (resume.location or "").lower()
    remote_policy = (jd.remote_policy or "").lower()

    if not job_location:
        return weight, "No location requirement; awarding full credit."
    if not candidate_location:
        partial = weight * 0.4
        return partial, "Candidate location not provided; giving partial credit."
    if job_location in candidate_location or candidate_location in job_location:
        return weight, "Candidate location aligns exactly with requirement."
    if "remote" in remote_policy or "hybrid" in remote_policy:
        partial = weight * 0.6
        return partial, "Remote/hybrid acceptable; partial credit for location mismatch."
    return 0.0, "Location mismatch and no remote option."


def _compute_education_component(resume: ResumeFeatures, weight: float) -> Tuple[float, str]:
    degrees = [degree.lower() for degree in resume.degrees]
    if not degrees:
        return weight * 0.3, "No degree detected; defaulting to partial credit."
    if any("phd" in degree or "doctor" in degree for degree in degrees):
        return weight, "Doctorate-level education"
    if any("master" in degree or "mba" in degree for degree in degrees):
        return weight * 0.9, "Graduate degree detected"
    if any("bachelor" in degree or degree in {"bs", "ba"} for degree in degrees):
        return weight * 0.75, "Bachelor-level education"
    return weight * 0.5, "Degree detected but level unclear"


def _compute_career_component(resume: ResumeFeatures, weight: float) -> Tuple[float, str]:
    positions = resume.positions
    if not positions:
        return weight * 0.4, "No role history parsed; awarding partial credit."
    unique_titles = {pos.get("title", "").lower() for pos in positions if pos.get("title")}
    promotions = max(len(unique_titles) - 1, 0)
    progression_factor = min(len(positions) / 4, 1.0)
    score = weight * (0.6 + 0.4 * min(promotions / 3, 1.0)) * progression_factor
    rationale = (
        f"{len(positions)} positions with {promotions} promotions inferred; "
        f"solid career progression."
    )
    return score, rationale


def _compute_achievements_component(resume: ResumeFeatures, weight: float) -> Tuple[float, str]:
    count = resume.achievements_count
    if count == 0:
        return weight * 0.3, "No quantified achievements detected."
    capped = min(count, 4)
    score = weight * (0.6 + 0.1 * capped)
    rationale = f"{count} quantified achievements captured."
    return min(score, weight), rationale


def _compute_skills_depth_component(resume: ResumeFeatures, weight: float) -> Tuple[float, str]:
    unique_skills = len(resume.skills)
    if unique_skills == 0:
        return weight * 0.2, "No skills extracted."
    if unique_skills >= 15:
        return weight, "Broad skill coverage (15+ skills)."
    if unique_skills >= 10:
        return weight * 0.85, "Strong skill coverage (10-14 skills)."
    if unique_skills >= 5:
        return weight * 0.65, "Moderate skill coverage (5-9 skills)."
    return weight * 0.4, "Limited skill coverage (<5 skills)."


def _apply_cap_if_needed(fit_score: float, has_missing_must_haves: bool, cap: float) -> float:
    if has_missing_must_haves:
        return min(fit_score, cap)
    return fit_score


def _normalize_component_weights(values: Dict[str, float]) -> Dict[str, float]:
    total = sum(values.values()) or 1.0
    return {key: (value / total) * 100.0 for key, value in values.items()}


def score_candidate(
    jd_features: JDFeatures,
    resume_features: ResumeFeatures,
    scoring_config: ScoringConfig | None = None,
) -> CandidateScore:
    config = scoring_config or jd_features.scoring_config
    fit_weights = _normalize_component_weights(config.fit_weights.model_dump())
    excellence_weights = _normalize_component_weights(config.excellence_weights.model_dump())
    final_weights = config.final_weights.normalized

    # Fit components
    must_have_score, must_have_rationale, coverage = _compute_must_have_component(
        jd_features, resume_features, fit_weights["must_have_skills"]
    )
    experience_score, experience_rationale = _compute_experience_component(
        jd_features, resume_features, fit_weights["experience"]
    )
    domain_score, domain_rationale, domain_match_ratio = _compute_domain_component(
        jd_features, resume_features, fit_weights["domain"]
    )
    location_score, location_rationale = _compute_location_component(
        jd_features, resume_features, fit_weights["location"]
    )

    fit_score_raw = must_have_score + experience_score + domain_score + location_score
    has_missing_must_haves = coverage < 1.0
    fit_score_capped = _apply_cap_if_needed(fit_score_raw, has_missing_must_haves, config.must_have_cap)

    fit_breakdown = {
        "must_have_skills": ScoreComponent(score=round(must_have_score, 1), rationale=must_have_rationale),
        "experience": ScoreComponent(score=round(experience_score, 1), rationale=experience_rationale),
        "domain": ScoreComponent(score=round(domain_score, 1), rationale=domain_rationale),
        "location": ScoreComponent(score=round(location_score, 1), rationale=location_rationale),
    }

    # Excellence components
    education_score, education_rationale = _compute_education_component(
        resume_features, excellence_weights["education"]
    )
    career_score, career_rationale = _compute_career_component(
        resume_features, excellence_weights["career_trajectory"]
    )
    achievements_score, achievements_rationale = _compute_achievements_component(
        resume_features, excellence_weights["achievements"]
    )
    skills_depth_score, skills_depth_rationale = _compute_skills_depth_component(
        resume_features, excellence_weights["skills_depth"]
    )

    excellence_score = (
        education_score + career_score + achievements_score + skills_depth_score
    )

    excellence_breakdown = {
        "education": ScoreComponent(score=round(education_score, 1), rationale=education_rationale),
        "career_trajectory": ScoreComponent(score=round(career_score, 1), rationale=career_rationale),
        "achievements": ScoreComponent(score=round(achievements_score, 1), rationale=achievements_rationale),
        "skills_depth": ScoreComponent(score=round(skills_depth_score, 1), rationale=skills_depth_rationale),
    }

    final_score = (
        fit_score_capped * final_weights["fit"]
        + excellence_score * final_weights["excellence"]
    )

    flags: List[str] = []
    if has_missing_must_haves:
        missing_skills = set(skill.lower() for skill in jd_features.required_skills) - set(
            skill.lower() for skill in resume_features.skills
        )
        flags.append(
            f"Missing must-have skills: {', '.join(sorted(missing_skills)) or 'unspecified'}"
        )
    if domain_match_ratio < 1.0 and jd_features.domains:
        flags.append("Partial domain fit")
    if not resume_features.location:
        flags.append("Location not provided")

    breakdown = ScoreBreakdown(
        fit=fit_breakdown,
        excellence=excellence_breakdown,
        flags=flags,
    )

    metadata = {
        "must_have_coverage": f"{coverage:.2f}",
        "domain_match": f"{domain_match_ratio:.2f}",
        "achievements_count": str(resume_features.achievements_count),
        "positions_count": str(len(resume_features.positions)),
    }

    return CandidateScore(
        fit_score=round(fit_score_capped, 1),
        excellence_score=round(excellence_score, 1),
        final_score=round(final_score, 1),
        breakdown=breakdown,
        metadata=metadata,
    )

