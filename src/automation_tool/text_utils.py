from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from rapidfuzz import fuzz, process

TAXONOMY_PATH = Path(__file__).resolve().parent / "domain_knowledge" / "skills_taxonomy.json"


@lru_cache(maxsize=1)
def load_taxonomy() -> Dict[str, object]:
    with TAXONOMY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    text = text.replace("\u2022", "\n").replace("\u00b7", "\n")
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def to_sentences(text: str) -> List[str]:
    normalized = normalize_text(text)
    candidates = re.split(r"(?<=[.!?])\s+(?=[A-Z])", normalized)
    sentences = [s.strip() for s in candidates if s.strip()]
    if not sentences:
        sentences = [line.strip() for line in normalized.splitlines() if line.strip()]
    return sentences


def to_tokens(text: str) -> List[str]:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9\s\+\.#]", " ", lowered)
    tokens = [tok for tok in lowered.split() if tok]
    return tokens


def extract_bullets(text: str) -> List[str]:
    lines = normalize_text(text).splitlines()
    bullets: List[str] = []
    for line in lines:
        cleaned = line.strip(" -•\t")
        if not cleaned:
            continue
        if line.lstrip().startswith(("-", "*", "•", "\u2022")) or len(cleaned.split()) <= 12:
            bullets.append(cleaned)
    return bullets


def extract_email(text: str) -> Optional[str]:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    match = re.search(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}", text)
    return match.group(0) if match else None


def extract_linkedin(text: str) -> Optional[str]:
    match = re.search(r"(https?://)?(www\.)?linkedin\.com/[A-Za-z0-9_/?=\-]+", text, re.IGNORECASE)
    return match.group(0) if match else None


def extract_location(text: str) -> Optional[str]:
    pattern = re.compile(
        r"\b(?:located in|location[:\s]|based in|relocation to)\s+([A-Za-z,\s]+)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip(" ,.")
    # fallback using simple heuristics (first line with comma)
    for line in normalize_text(text).splitlines()[:5]:
        if "," in line and len(line.split()) <= 6:
            return line.strip()
    return None


def extract_years_of_experience(text: str) -> Optional[float]:
    pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:years|yrs)", re.IGNORECASE)
    matches = [float(m.group(1)) for m in pattern.finditer(text)]
    if matches:
        return max(matches)
    return None


def detect_seniority(text: str) -> Optional[str]:
    taxonomy = load_taxonomy()
    markers: Dict[str, List[str]] = taxonomy.get("seniority_markers", {})  # type: ignore[assignment]
    lowered = text.lower()
    best_match: Tuple[str, int] | None = None
    for level, keywords in markers.items():
        for keyword in keywords:
            if keyword in lowered:
                score = len(keyword)
                if not best_match or score > best_match[1]:
                    best_match = (level, score)
    return best_match[0] if best_match else None


def _flatten_skills() -> Set[str]:
    taxonomy = load_taxonomy()
    skills: Dict[str, Iterable[str]] = taxonomy.get("skills", {})  # type: ignore[assignment]
    combined: Set[str] = set()
    for values in skills.values():
        combined.update(v.lower() for v in values)
    return combined


@lru_cache(maxsize=1)
def get_skill_vocab() -> Set[str]:
    return _flatten_skills()


def extract_skills(text: str, threshold: int = 85) -> List[str]:
    tokens = set(to_tokens(text))
    vocabulary = get_skill_vocab()

    direct_matches = vocabulary.intersection(tokens)
    remaining = vocabulary - direct_matches

    fuzzy_matches = set()
    for token in tokens:
        if len(token) <= 2:
            continue
        match, score, _ = process.extractOne(
            token,
            remaining,
            scorer=fuzz.ratio,
        ) or (None, 0, None)
        if match and score >= threshold:
            fuzzy_matches.add(match)

    skills = sorted({*direct_matches, *fuzzy_matches})
    return skills


def extract_domains(text: str) -> List[str]:
    taxonomy = load_taxonomy()
    domains: Dict[str, Iterable[str]] = taxonomy.get("domains", {})  # type: ignore[assignment]
    lowered = text.lower()
    detected = []
    for domain, keywords in domains.items():
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                detected.append(domain)
                break
    return sorted(set(detected))


def extract_degrees(text: str) -> List[str]:
    taxonomy = load_taxonomy()
    degrees: Iterable[str] = taxonomy.get("degrees", [])  # type: ignore[assignment]
    lowered = text.lower()
    detected = [
        degree
        for degree in degrees
        if re.search(rf"\b{re.escape(degree)}\b", lowered)
    ]
    return sorted(set(detected))


def extract_certifications(text: str) -> List[str]:
    taxonomy = load_taxonomy()
    certs: Iterable[str] = taxonomy.get("certifications", [])  # type: ignore[assignment]
    lowered = text.lower()
    detected = [
        cert
        for cert in certs
        if re.search(rf"\b{re.escape(cert)}\b", lowered)
    ]
    return sorted(set(detected))


def extract_bullet_sections(text: str, headers: Iterable[str]) -> List[str]:
    normalized = normalize_text(text)
    lines = normalized.splitlines()
    results: List[str] = []
    header_pattern = re.compile(
        r"|".join(rf"^{re.escape(h)}[:\s]*$" for h in headers),
        re.IGNORECASE,
    )
    capture = False
    for line in lines:
        if header_pattern.match(line.strip()):
            capture = True
            continue
        if capture:
            if line.strip() == "" or re.match(r"^[A-Za-z].*:$", line):
                capture = False
                continue
            results.append(line.strip())
    if not results and headers:
        # fallback: collect lines containing header keywords
        for line in lines:
            for header in headers:
                if header.lower() in line.lower():
                    results.append(line.strip())
                    break
    return [r.strip(" -•") for r in results if r.strip()]


def deduplicate_preserve_order(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(item)
    return ordered


def extract_numeric_achievements(text: str) -> List[str]:
    lines = normalize_text(text).splitlines()
    achievements = []
    for line in lines:
        if re.search(r"\b\d+%|\$\d+|\d{4}|\d+\s*(?:million|billion|k)\b", line.lower()):
            achievements.append(line.strip())
    return achievements


def emphasize_keywords(text: str, keywords: Iterable[str]) -> str:
    highlighted = text
    for keyword in keywords:
        highlighted = re.sub(
            rf"({re.escape(keyword)})",
            r"**\1**",
            highlighted,
            flags=re.IGNORECASE,
        )
    return highlighted

