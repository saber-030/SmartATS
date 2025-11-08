from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FitWeights(BaseModel):
    must_have_skills: float = Field(40.0, ge=0)
    experience: float = Field(30.0, ge=0)
    domain: float = Field(20.0, ge=0)
    location: float = Field(10.0, ge=0)

    @property
    def total(self) -> float:
        return (
            self.must_have_skills
            + self.experience
            + self.domain
            + self.location
        )


class ExcellenceWeights(BaseModel):
    education: float = Field(25.0, ge=0)
    career_trajectory: float = Field(25.0, ge=0)
    achievements: float = Field(25.0, ge=0)
    skills_depth: float = Field(25.0, ge=0)

    @property
    def total(self) -> float:
        return (
            self.education
            + self.career_trajectory
            + self.achievements
            + self.skills_depth
        )


class FinalWeights(BaseModel):
    fit: float = Field(0.7, ge=0, le=1)
    excellence: float = Field(0.3, ge=0, le=1)

    @property
    def normalized(self) -> Dict[str, float]:
        total = self.fit + self.excellence
        if total == 0:
            return {"fit": 0.0, "excellence": 0.0}
        return {"fit": self.fit / total, "excellence": self.excellence / total}


class ScoringConfig(BaseModel):
    fit_weights: FitWeights = Field(default_factory=FitWeights)
    excellence_weights: ExcellenceWeights = Field(default_factory=ExcellenceWeights)
    final_weights: FinalWeights = Field(default_factory=FinalWeights)
    must_have_cap: float = Field(50.0, ge=0, le=100)
    tie_breakers: List[str] = Field(
        default_factory=lambda: [
            "must_have_coverage",
            "domain_match",
            "career_trajectory",
            "achievements",
        ]
    )


class JDFeatures(BaseModel):
    title: str
    raw_text: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    keywords_critical: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    req_years_overall: Optional[float] = None
    req_years_domain: Optional[float] = None
    seniority: Optional[str] = None
    required_degrees: List[str] = Field(default_factory=list)
    preferred_degrees: List[str] = Field(default_factory=list)
    required_certs: List[str] = Field(default_factory=list)
    preferred_certs: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    employment_type: Optional[str] = None
    remote_policy: Optional[str] = None
    additional_criteria: Dict[str, str] = Field(default_factory=dict)
    scoring_config: ScoringConfig = Field(default_factory=ScoringConfig)
    metadata: Dict[str, str] = Field(default_factory=dict)


class ResumeFeatures(BaseModel):
    candidate_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    overall_years_experience: Optional[float] = None
    domain_years_experience: Optional[float] = None
    seniority: Optional[str] = None
    degrees: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    achievements_count: int = 0
    positions: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    raw_text: str = ""
    extracted_keywords: List[str] = Field(default_factory=list)


class ScoreComponent(BaseModel):
    score: float
    rationale: str


class ScoreBreakdown(BaseModel):
    fit: Dict[str, ScoreComponent]
    excellence: Dict[str, ScoreComponent]
    flags: List[str] = Field(default_factory=list)


class CandidateScore(BaseModel):
    fit_score: float
    excellence_score: float
    final_score: float
    breakdown: ScoreBreakdown
    metadata: Dict[str, str] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class JobRecord(BaseModel):
    job_id: str
    created_at: datetime
    updated_at: datetime
    features: JDFeatures


class CandidateRecord(BaseModel):
    candidate_id: str
    job_id: str
    created_at: datetime
    updated_at: datetime
    resume: ResumeFeatures
    score: CandidateScore
    status: str = "active"

