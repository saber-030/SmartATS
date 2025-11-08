from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from .data_models import JDFeatures
from .text_utils import (
    deduplicate_preserve_order,
    detect_seniority,
    extract_bullet_sections,
    extract_certifications,
    extract_degrees,
    extract_domains,
    extract_location,
    extract_skills,
    extract_years_of_experience,
    normalize_text,
    to_tokens,
)

STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "that",
    "will",
    "you",
    "your",
    "team",
    "our",
    "are",
    "in",
    "to",
    "of",
    "as",
    "on",
    "be",
    "we",
    "a",
    "an",
    "or",
    "by",
    "is",
    "this",
    "role",
    "responsibilities",
    "responsibility",
    "skills",
    "experience",
    "must",
    "have",
    "preferred",
    "nice",
    "requirements",
}


SECTION_HEADERS = {
    "required": [
        "Must have",
        "Must-have",
        "Required Skills",
        "Requirements",
        "Basic Qualifications",
        "What you bring",
    ],
    "preferred": [
        "Nice to have",
        "Preferred",
        "Preferred Skills",
        "Preferred Qualifications",
        "Bonus",
    ],
    "responsibilities": [
        "Responsibilities",
        "What you'll do",
        "Key Responsibilities",
        "Duties",
        "Day to day",
    ],
}


def _split_required_preferred(required_raw: List[str], preferred_raw: List[str]) -> Dict[str, List[str]]:
    required = []
    preferred = []
    for item in required_raw:
        if item.lower().startswith(("preferred", "nice to have")):
            preferred.append(item)
        else:
            required.append(item)
    required.extend([i for i in required_raw if i not in required])
    preferred.extend([i for i in preferred_raw if i not in preferred])
    return {
        "required": deduplicate_preserve_order(required),
        "preferred": deduplicate_preserve_order(preferred),
    }


def _extract_keywords(text: str, exclude: List[str], top_k: int = 15) -> List[str]:
    tokens = [tok for tok in to_tokens(text) if tok not in STOPWORDS]
    exclude_set = {e.lower() for e in exclude}
    filtered = [tok for tok in tokens if tok not in exclude_set]
    counts = Counter(filtered)
    most_common = [token for token, _ in counts.most_common(top_k)]
    return most_common


def parse_job_description(
    title: str,
    raw_text: str,
    recruiter_inputs: Optional[Dict[str, str | List[str]]] = None,
) -> JDFeatures:
    normalized = normalize_text(raw_text)
    recruiter_inputs = recruiter_inputs or {}

    required_lines = extract_bullet_sections(normalized, SECTION_HEADERS["required"])
    preferred_lines = extract_bullet_sections(normalized, SECTION_HEADERS["preferred"])
    responsibility_lines = extract_bullet_sections(normalized, SECTION_HEADERS["responsibilities"])

    skills_detected = extract_skills(normalized)
    required_split = _split_required_preferred(required_lines, preferred_lines)

    structured_required = required_split["required"] or deduplicate_preserve_order(skills_detected[:10])
    structured_preferred = (
        required_split["preferred"]
        or deduplicate_preserve_order(skills_detected[10:20])
    )

    location = recruiter_inputs.get("location") or extract_location(normalized)
    req_years_overall = recruiter_inputs.get("req_years_overall") or extract_years_of_experience(normalized)
    req_years_domain = recruiter_inputs.get("req_years_domain") or None

    required_degrees = recruiter_inputs.get("required_degrees") or extract_degrees(normalized)
    preferred_degrees = recruiter_inputs.get("preferred_degrees") or []

    required_certs = recruiter_inputs.get("required_certs") or extract_certifications(normalized)
    preferred_certs = recruiter_inputs.get("preferred_certs") or []

    domains = recruiter_inputs.get("domains") or extract_domains(normalized)
    seniority = recruiter_inputs.get("seniority") or detect_seniority(f"{title}\n{normalized}")

    responsibilities = deduplicate_preserve_order(responsibility_lines)
    keywords = _extract_keywords(
        normalized,
        exclude=[*structured_required, *structured_preferred],
    )

    metadata: Dict[str, str] = {}
    if recruiter_inputs.get("experience_level"):
        metadata["experience_level"] = str(recruiter_inputs["experience_level"])
    if recruiter_inputs.get("employment_type"):
        metadata["employment_type"] = str(recruiter_inputs["employment_type"])
    if recruiter_inputs.get("remote_policy"):
        metadata["remote_policy"] = str(recruiter_inputs["remote_policy"])

    jd_features = JDFeatures(
        title=title,
        raw_text=normalized,
        required_skills=deduplicate_preserve_order(structured_required),
        preferred_skills=deduplicate_preserve_order(structured_preferred),
        responsibilities=responsibilities,
        keywords_critical=keywords,
        domains=domains if isinstance(domains, list) else [str(domains)],
        req_years_overall=float(req_years_overall) if req_years_overall else None,
        req_years_domain=float(req_years_domain) if req_years_domain else None,
        seniority=seniority,
        required_degrees=deduplicate_preserve_order(
            required_degrees if isinstance(required_degrees, list) else [str(required_degrees)]
        ),
        preferred_degrees=deduplicate_preserve_order(
            preferred_degrees if isinstance(preferred_degrees, list) else [str(preferred_degrees)]
        ),
        required_certs=deduplicate_preserve_order(
            required_certs if isinstance(required_certs, list) else [str(required_certs)]
        ),
        preferred_certs=deduplicate_preserve_order(
            preferred_certs if isinstance(preferred_certs, list) else [str(preferred_certs)]
        ),
        location=str(location) if location else None,
        remote_policy=str(recruiter_inputs.get("remote_policy") or ""),
        employment_type=str(recruiter_inputs.get("employment_type") or ""),
        additional_criteria={
            key: ", ".join(value) if isinstance(value, list) else str(value)
            for key, value in recruiter_inputs.items()
            if key
            not in {
                "location",
                "req_years_overall",
                "req_years_domain",
                "required_degrees",
                "preferred_degrees",
                "required_certs",
                "preferred_certs",
                "domains",
                "seniority",
                "employment_type",
                "remote_policy",
                "experience_level",
            }
            and value
        },
    )

    return jd_features

