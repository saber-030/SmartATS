from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session, mapped_column, relationship, scoped_session, sessionmaker

from .data_models import CandidateRecord, CandidateScore, JDFeatures, JobRecord, ResumeFeatures

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "automation.db"


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: str = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: str = mapped_column(String, nullable=False)
    features: dict = mapped_column(JSON, nullable=False)
    raw_text: str = mapped_column(Text, nullable=False)
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    candidates = relationship("Candidate", back_populates="job", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    id: str = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: str = mapped_column(String, ForeignKey("jobs.id"), nullable=False)
    name: str = mapped_column(String, nullable=False)
    resume_features: dict = mapped_column(JSON, nullable=False)
    score: dict = mapped_column(JSON, nullable=False)
    raw_text: str = mapped_column(Text, nullable=False)
    status: str = mapped_column(
        Enum("active", "rejected", "withdrawn", "advanced", name="candidate_status"),
        default="active",
        nullable=False,
    )
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="candidates")


class StorageManager:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False, future=True)
        self.session_factory = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False)
        self.scoped_session = scoped_session(self.session_factory)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session = self.scoped_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Job operations
    def create_job(self, features: JDFeatures) -> JobRecord:
        job = Job(
            title=features.title,
            features=json.loads(features.model_dump_json()),
            raw_text=features.raw_text,
        )
        with self.get_session() as session:
            session.add(job)
            session.flush()
            record = JobRecord(
                job_id=job.id,
                created_at=job.created_at,
                updated_at=job.updated_at,
                features=features,
            )
        return record

    def update_job(self, job_id: str, features: JDFeatures) -> JobRecord:
        with self.get_session() as session:
            job: Job | None = session.get(Job, job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            job.title = features.title
            job.features = json.loads(features.model_dump_json())
            job.raw_text = features.raw_text
            job.updated_at = datetime.utcnow()
            session.add(job)
            record = JobRecord(
                job_id=job.id,
                created_at=job.created_at,
                updated_at=job.updated_at,
                features=features,
            )
        return record

    def list_jobs(self) -> List[JobRecord]:
        with self.get_session() as session:
            stmt = select(Job).order_by(Job.created_at.desc())
            jobs = session.scalars(stmt).all()
            return [
                JobRecord(
                    job_id=job.id,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    features=JDFeatures.model_validate(job.features),
                )
                for job in jobs
            ]

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self.get_session() as session:
            job: Job | None = session.get(Job, job_id)
            if not job:
                return None
            return JobRecord(
                job_id=job.id,
                created_at=job.created_at,
                updated_at=job.updated_at,
                features=JDFeatures.model_validate(job.features),
            )

    # Candidate operations
    def add_candidate(
        self,
        job_id: str,
        resume: ResumeFeatures,
        score: CandidateScore,
    ) -> CandidateRecord:
        candidate = Candidate(
            job_id=job_id,
            name=resume.candidate_name,
            resume_features=json.loads(resume.model_dump_json()),
            score=json.loads(score.model_dump_json()),
            raw_text=resume.raw_text,
        )
        with self.get_session() as session:
            session.add(candidate)
            session.flush()
            record = CandidateRecord(
                candidate_id=candidate.id,
                job_id=job_id,
                created_at=candidate.created_at,
                updated_at=candidate.updated_at,
                resume=resume,
                score=score,
                status=candidate.status,
            )
        return record

    def list_candidates(self, job_id: str) -> List[CandidateRecord]:
        with self.get_session() as session:
            stmt = select(Candidate).where(Candidate.job_id == job_id)
            candidates = session.scalars(stmt).all()
            return [
                CandidateRecord(
                    candidate_id=candidate.id,
                    job_id=candidate.job_id,
                    created_at=candidate.created_at,
                    updated_at=candidate.updated_at,
                    resume=ResumeFeatures.model_validate(candidate.resume_features),
                    score=CandidateScore.model_validate(candidate.score),
                    status=candidate.status,
                )
                for candidate in candidates
            ]

    def update_candidate_status(self, candidate_id: str, status: str) -> CandidateRecord:
        if status not in {"active", "rejected", "withdrawn", "advanced"}:
            raise ValueError(f"Unsupported status: {status}")
        with self.get_session() as session:
            candidate: Candidate | None = session.get(Candidate, candidate_id)
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")
            candidate.status = status
            candidate.updated_at = datetime.utcnow()
            session.add(candidate)
            record = CandidateRecord(
                candidate_id=candidate.id,
                job_id=candidate.job_id,
                created_at=candidate.created_at,
                updated_at=candidate.updated_at,
                resume=ResumeFeatures.model_validate(candidate.resume_features),
                score=CandidateScore.model_validate(candidate.score),
                status=candidate.status,
            )
        return record

    def delete_candidate(self, candidate_id: str) -> None:
        with self.get_session() as session:
            candidate: Candidate | None = session.get(Candidate, candidate_id)
            if candidate:
                session.delete(candidate)

    def update_candidate_score(self, candidate_id: str, score: CandidateScore) -> CandidateRecord:
        with self.get_session() as session:
            candidate: Candidate | None = session.get(Candidate, candidate_id)
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")
            candidate.score = json.loads(score.model_dump_json())
            candidate.updated_at = datetime.utcnow()
            session.add(candidate)
            record = CandidateRecord(
                candidate_id=candidate.id,
                job_id=candidate.job_id,
                created_at=candidate.created_at,
                updated_at=candidate.updated_at,
                resume=ResumeFeatures.model_validate(candidate.resume_features),
                score=score,
                status=candidate.status,
            )
        return record

