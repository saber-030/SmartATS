from __future__ import annotations

import re
from typing import Dict, List, Optional

from .data_models import ResumeFeatures
from .text_utils import (
    deduplicate_preserve_order,
    detect_seniority,
    extract_certifications,
    extract_degrees,
    extract_domains,
    extract_email,
    extract_linkedin,
    extract_location,
    extract_numeric_achievements,
    extract_phone,
    extract_skills,
    extract_years_of_experience,
    normalize_text,
)


def _guess_name_from_text(text: str) -> str:
    lines = [line.strip() for line in normalize_text(text).splitlines() if line.strip()]
    if not lines:
        return "Unknown Candidate"
    first_line = lines[0]
    words = first_line.split()
    if len(words) <= 5:
        return first_line.title()
    # fallback: look for uppercase line
    for line in lines[:5]:
        if line.isupper():
            return line.title()
    return first_line.title()


def _extract_positions(text: str) -> List[Dict[str, Optional[str]]]:
    positions: List[Dict[str, Optional[str]]] = []
    pattern = re.compile(
        r"(?P<title>.+?)\s*(?:at|-)\s*(?P<company>[A-Za-z0-9 &.,]+)\s*(?P<dates>\d{4}.*\d{4}|Present)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        positions.append(
            {
                "title": match.group("title").strip(),
                "company": match.group("company").strip() if match.group("company") else None,
                "dates": match.group("dates").strip() if match.group("dates") else None,
            }
        )
    return positions


def _estimate_domain_years(domains: List[str], positions: List[Dict[str, Optional[str]]]) -> Optional[float]:
    if not domains or not positions:
        return None
    # heuristic: assume 2 years per relevant position
    relevant_positions = [
        pos for pos in positions if any(domain.lower() in (pos.get("company") or "").lower() for domain in domains)
    ]
    if not relevant_positions:
        return None
    return float(len(relevant_positions) * 2)


def parse_resume(raw_text: str, overrides: Optional[Dict[str, str | List[str]]] = None) -> ResumeFeatures:
    normalized = normalize_text(raw_text)
    overrides = overrides or {}

    name = overrides.get("candidate_name") or _guess_name_from_text(normalized)
    email = overrides.get("email") or extract_email(normalized)
    phone = overrides.get("phone") or extract_phone(normalized)
    linkedin = overrides.get("linkedin") or extract_linkedin(normalized)
    location = overrides.get("location") or extract_location(normalized)

    skills = deduplicate_preserve_order(
        overrides.get("skills") or extract_skills(normalized)
    )
    preferred_skills = deduplicate_preserve_order(
        overrides.get("preferred_skills") or []
    )
    domains = deduplicate_preserve_order(
        overrides.get("domains") or extract_domains(normalized)
    )
    degrees = deduplicate_preserve_order(
        overrides.get("degrees") or extract_degrees(normalized)
    )
    certifications = deduplicate_preserve_order(
        overrides.get("certifications") or extract_certifications(normalized)
    )
    achievements = deduplicate_preserve_order(
        overrides.get("achievements") or extract_numeric_achievements(normalized)
    )
    positions = overrides.get("positions") or _extract_positions(normalized)

    overall_years = overrides.get("overall_years_experience") or extract_years_of_experience(normalized)
    domain_years = overrides.get("domain_years_experience") or _estimate_domain_years(domains, positions)
    seniority = overrides.get("seniority") or detect_seniority(normalized)

    resume_features = ResumeFeatures(
        candidate_name=str(name),
        email=email,
        phone=phone,
        linkedin=linkedin,
        location=str(location) if location else None,
        skills=skills,
        preferred_skills=preferred_skills,
        responsibilities=[],
        domains=domains,
        overall_years_experience=float(overall_years) if overall_years else None,
        domain_years_experience=float(domain_years) if domain_years else None,
        seniority=seniority,
        degrees=degrees,
        certifications=certifications,
        achievements=achievements,
        achievements_count=len(achievements),
        positions=positions if isinstance(positions, list) else [],
        raw_text=normalized,
        extracted_keywords=skills,
    )

    return resume_features

