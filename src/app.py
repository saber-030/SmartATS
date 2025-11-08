from __future__ import annotations

import io
from typing import Dict, List, Optional

import streamlit as st

from automation_tool.data_models import (
    ExcellenceWeights,
    FinalWeights,
    FitWeights,
    JDFeatures,
    ScoringConfig,
)
from automation_tool.file_ingest import UnsupportedFileTypeError, read_uploaded_file
from automation_tool.jd_parser import parse_job_description
from automation_tool.ranking_service import candidates_to_dataframe, sort_candidates
from automation_tool.resume_parser import parse_resume
from automation_tool.scoring import score_candidate
from automation_tool.storage import StorageManager


@st.cache_resource
def get_storage() -> StorageManager:
    return StorageManager()


def parse_list_input(value: str) -> List[str]:
    if not value:
        return []
    parts = []
    for line in value.splitlines():
        for item in line.split(","):
            item_clean = item.strip()
            if item_clean:
                parts.append(item_clean)
    return parts


def gather_job_text(file_buffer: Optional[io.BytesIO], text_input: str, filename: Optional[str]) -> str:
    if file_buffer is not None:
        file_buffer.seek(0)
        return read_uploaded_file(file_buffer, filename)
    return text_input


def render_job_creation(storage: StorageManager) -> Optional[str]:
    st.header("Create New Job Description")
    with st.form("create_job_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        title = col1.text_input("Job Title*", placeholder="e.g., Senior Data Scientist")
        location = col2.text_input("Location", placeholder="e.g., San Francisco, CA or Remote")
        experience_years = col1.number_input(
            "Required Overall Experience (years)",
            min_value=0.0,
            max_value=50.0,
            value=0.0,
            help="Specify minimum years of experience expected for the role.",
        )
        domain_input = col2.text_input(
            "Domain / Industry Focus",
            placeholder="e.g., FinTech, Healthcare",
        )
        remote_policy = col1.selectbox(
            "Remote Policy",
            options=["", "Remote", "Hybrid", "Onsite"],
            help="Used to grant partial credit if candidates are remote-ready.",
        )
        employment_type = col2.selectbox(
            "Employment Type",
            options=["", "Full-time", "Contract", "Part-time", "Internship"],
        )

        st.markdown("#### Job Description Source")
        uploaded_file = st.file_uploader("Upload JD (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"], key="jd_upload")
        jd_text_area = st.text_area(
            "Or paste job description text",
            height=200,
            placeholder="Paste the job description here if no file is uploaded.",
        )

        st.markdown("#### Structured Inputs (Optional overrides)")
        required_skills_input = st.text_area(
            "Must-have Skills (comma or newline separated)",
            placeholder="Python, Machine Learning, SQL",
        )
        preferred_skills_input = st.text_area(
            "Nice-to-have Skills",
            placeholder="AWS, Tableau",
        )
        responsibilities_input = st.text_area(
            "Responsibilities",
            placeholder="Build predictive models...\nPartner with stakeholders...",
        )
        required_degrees_input = st.text_input(
            "Required Degrees",
            placeholder="Bachelor, Master",
        )
        preferred_degrees_input = st.text_input(
            "Preferred Degrees",
            placeholder="PhD, MBA",
        )
        required_certs_input = st.text_input(
            "Required Certifications",
            placeholder="PMP, AWS Certified",
        )
        preferred_certs_input = st.text_input(
            "Preferred Certifications",
            placeholder="Six Sigma",
        )

        st.markdown("#### Scoring Configuration (Optional)")
        with st.expander("Fit Score Weights"):
            fit_col1, fit_col2 = st.columns(2)
            fit_must = fit_col1.number_input("Must-have Skills Weight", min_value=0.0, max_value=100.0, value=40.0)
            fit_exp = fit_col2.number_input("Experience Weight", min_value=0.0, max_value=100.0, value=30.0)
            fit_domain = fit_col1.number_input("Domain/Industry Weight", min_value=0.0, max_value=100.0, value=20.0)
            fit_location = fit_col2.number_input("Location Weight", min_value=0.0, max_value=100.0, value=10.0)

        with st.expander("Excellence Score Weights"):
            exc_col1, exc_col2 = st.columns(2)
            exc_edu = exc_col1.number_input("Education Weight", min_value=0.0, max_value=100.0, value=25.0)
            exc_career = exc_col2.number_input("Career Trajectory Weight", min_value=0.0, max_value=100.0, value=25.0)
            exc_achievements = exc_col1.number_input("Achievements Weight", min_value=0.0, max_value=100.0, value=25.0)
            exc_skills = exc_col2.number_input("Skills Depth Weight", min_value=0.0, max_value=100.0, value=25.0)

        fit_vs_excel = st.slider(
            "Final score weighting (Fit vs Excellence)",
            min_value=0,
            max_value=100,
            value=70,
            format="%d%% fit",
        )
        must_have_cap = st.number_input(
            "Maximum Fit Score if Must-have skills missing",
            min_value=10.0,
            max_value=100.0,
            value=50.0,
        )

        submitted = st.form_submit_button("Create Job")

    if not submitted:
        return None

    if not title:
        st.error("Job title is required.")
        return None

    jd_text = gather_job_text(
        uploaded_file if uploaded_file is None else io.BytesIO(uploaded_file.getvalue()),
        jd_text_area,
        uploaded_file.name if uploaded_file else None,
    )

    if not jd_text:
        st.error("Please provide job description text or upload a file.")
        return None

    recruiter_inputs: Dict[str, str | List[str]] = {
        "location": location,
        "req_years_overall": experience_years if experience_years > 0 else None,
        "domains": parse_list_input(domain_input),
        "remote_policy": remote_policy,
        "employment_type": employment_type,
        "required_degrees": parse_list_input(required_degrees_input),
        "preferred_degrees": parse_list_input(preferred_degrees_input),
        "required_certs": parse_list_input(required_certs_input),
        "preferred_certs": parse_list_input(preferred_certs_input),
    }

    try:
        jd_features = parse_job_description(title=title, raw_text=jd_text, recruiter_inputs=recruiter_inputs)
    except UnsupportedFileTypeError as exc:
        st.error(str(exc))
        return None
    except Exception as exc:  # pylint: disable=broad-except
        st.error(f"Failed to parse job description: {exc}")
        return None

    required_skills_override = parse_list_input(required_skills_input)
    preferred_skills_override = parse_list_input(preferred_skills_input)
    responsibilities_override = parse_list_input(responsibilities_input)

    if required_skills_override:
        jd_features.required_skills = required_skills_override
    if preferred_skills_override:
        jd_features.preferred_skills = preferred_skills_override
    if responsibilities_override:
        jd_features.responsibilities = responsibilities_override
    if location:
        jd_features.location = location
    if experience_years:
        jd_features.req_years_overall = experience_years
    if domain_input:
        jd_features.domains = parse_list_input(domain_input)
    if remote_policy:
        jd_features.remote_policy = remote_policy
    if employment_type:
        jd_features.employment_type = employment_type

    scoring_config = ScoringConfig(
        fit_weights=FitWeights(
            must_have_skills=fit_must,
            experience=fit_exp,
            domain=fit_domain,
            location=fit_location,
        ),
        excellence_weights=ExcellenceWeights(
            education=exc_edu,
            career_trajectory=exc_career,
            achievements=exc_achievements,
            skills_depth=exc_skills,
        ),
        final_weights=FinalWeights(
            fit=fit_vs_excel / 100,
            excellence=(100 - fit_vs_excel) / 100,
        ),
        must_have_cap=must_have_cap,
    )
    jd_features.scoring_config = scoring_config

    record = storage.create_job(jd_features)
    st.success(f"Job '{jd_features.title}' created successfully.")
    return record.job_id


def render_job_summary(job: JDFeatures) -> None:
    st.subheader(job.title)
    cols = st.columns(4)
    cols[0].metric("Location", job.location or "Not specified")
    cols[1].metric("Required Exp (yrs)", job.req_years_overall or "N/A")
    cols[2].metric("Domains", ", ".join(job.domains) or "N/A")
    cols[3].metric("Must-have skills", len(job.required_skills))

    st.markdown("**Must-have Skills**")
    st.write(", ".join(job.required_skills) or "_None captured_")
    st.markdown("**Nice-to-have Skills**")
    st.write(", ".join(job.preferred_skills) or "_None captured_")
    st.markdown("**Responsibilities**")
    st.write("\n".join(f"- {item}" for item in job.responsibilities) or "_None captured_")
    st.markdown("**Critical Keywords**")
    st.write(", ".join(job.keywords_critical) or "_None captured_")


def render_job_edit(storage: StorageManager, job_id: str, job: JDFeatures) -> JDFeatures:
    with st.expander("Edit job definition & scoring", expanded=False):
        with st.form(f"edit_job_{job_id}"):
            col1, col2 = st.columns(2)
            title = col1.text_input("Job Title", value=job.title)
            location = col2.text_input("Location", value=job.location or "")
            req_years = col1.number_input(
                "Required Overall Experience (years)",
                min_value=0.0,
                max_value=50.0,
                value=float(job.req_years_overall or 0.0),
            )
            domains = col2.text_input(
                "Domains / Industries",
                value=", ".join(job.domains),
            )
            remote_policy = col1.text_input("Remote Policy", value=job.remote_policy or "")
            employment_type = col2.text_input("Employment Type", value=job.employment_type or "")

            required_skills = st.text_area(
                "Must-have Skills",
                value=", ".join(job.required_skills),
            )
            preferred_skills = st.text_area(
                "Nice-to-have Skills",
                value=", ".join(job.preferred_skills),
            )
            responsibilities = st.text_area(
                "Responsibilities",
                value="\n".join(job.responsibilities),
            )

            st.markdown("**Fit Score Weights**")
            fit_col1, fit_col2 = st.columns(2)
            fit_must = fit_col1.number_input(
                "Must-have Skills Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.fit_weights.must_have_skills),
            )
            fit_exp = fit_col2.number_input(
                "Experience Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.fit_weights.experience),
            )
            fit_domain = fit_col1.number_input(
                "Domain/Industry Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.fit_weights.domain),
            )
            fit_location = fit_col2.number_input(
                "Location Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.fit_weights.location),
            )

            st.markdown("**Excellence Score Weights**")
            exc_col1, exc_col2 = st.columns(2)
            exc_edu = exc_col1.number_input(
                "Education Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.excellence_weights.education),
            )
            exc_career = exc_col2.number_input(
                "Career Trajectory Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.excellence_weights.career_trajectory),
            )
            exc_achievements = exc_col1.number_input(
                "Achievements Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.excellence_weights.achievements),
            )
            exc_skills = exc_col2.number_input(
                "Skills Depth Weight",
                min_value=0.0,
                max_value=100.0,
                value=float(job.scoring_config.excellence_weights.skills_depth),
            )

            fit_vs_excel = st.slider(
                "Final weighting (Fit vs Excellence)",
                min_value=0,
                max_value=100,
                value=int(job.scoring_config.final_weights.fit * 100),
            )
            must_have_cap = st.number_input(
                "Fit score cap when missing must-haves",
                min_value=10.0,
                max_value=100.0,
                value=float(job.scoring_config.must_have_cap),
            )

            submitted = st.form_submit_button("Save updates & rescore candidates")

        if not submitted:
            return job

        updated = job.model_copy()
        updated.title = title
        updated.location = location or None
        updated.req_years_overall = req_years if req_years else None
        updated.domains = parse_list_input(domains)
        updated.remote_policy = remote_policy or None
        updated.employment_type = employment_type or None
        updated.required_skills = parse_list_input(required_skills)
        updated.preferred_skills = parse_list_input(preferred_skills)
        updated.responsibilities = parse_list_input(responsibilities)
        updated.scoring_config = ScoringConfig(
            fit_weights=FitWeights(
                must_have_skills=fit_must,
                experience=fit_exp,
                domain=fit_domain,
                location=fit_location,
            ),
            excellence_weights=ExcellenceWeights(
                education=exc_edu,
                career_trajectory=exc_career,
                achievements=exc_achievements,
                skills_depth=exc_skills,
            ),
            final_weights=FinalWeights(
                fit=fit_vs_excel / 100,
                excellence=(100 - fit_vs_excel) / 100,
            ),
            must_have_cap=must_have_cap,
        )

        storage.update_job(job_id, updated)
        st.success("Job updated. Re-scoring existing candidates...")

        candidates = storage.list_candidates(job_id)
        for record in candidates:
            new_score = score_candidate(updated, record.resume, updated.scoring_config)
            storage.update_candidate_score(record.candidate_id, new_score)

        st.info("All candidates rescored with updated configuration.")
        return updated

    return job


def render_resume_ingest(storage: StorageManager, job_id: str, job: JDFeatures) -> None:
    st.subheader("Add Candidates")
    with st.form(f"resume_upload_{job_id}"):
        uploads = st.file_uploader(
            "Upload resumes (PDF/DOCX/TXT)",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
        )
        submit = st.form_submit_button("Process & Score Resumes")

    if not submit or not uploads:
        return

    success_count = 0
    for upload in uploads:
        try:
            content = read_uploaded_file(io.BytesIO(upload.getvalue()), upload.name)
            resume = parse_resume(content)
            score = score_candidate(job, resume, job.scoring_config)
            storage.add_candidate(job_id, resume, score)
            success_count += 1
        except UnsupportedFileTypeError as exc:
            st.warning(f"{upload.name}: {exc}")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Failed to process {upload.name}: {exc}")

    if success_count:
        st.success(f"Successfully processed {success_count} resumes.")


def render_candidate_dashboard(storage: StorageManager, job_id: str, job: JDFeatures) -> None:
    st.subheader("Ranked Candidates")
    candidates = sort_candidates(storage.list_candidates(job_id))

    if not candidates:
        st.info("No candidates have been processed for this role yet.")
        return

    status_filter = st.multiselect(
        "Filter by candidate status",
        options=["active", "rejected", "withdrawn", "advanced"],
        default=["active"],
    )

    filtered = [candidate for candidate in candidates if candidate.status in status_filter]
    df = candidates_to_dataframe(filtered)
    st.dataframe(
        df.drop(columns=["Candidate ID"]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("### Candidate Details & Actions")
    for record in filtered:
        with st.expander(f"{record.resume.candidate_name} — Final Score {record.score.final_score}"):
            col1, col2 = st.columns(2)
            col1.write(f"**Email:** {record.resume.email or 'N/A'}")
            col1.write(f"**Phone:** {record.resume.phone or 'N/A'}")
            col1.write(f"**Location:** {record.resume.location or 'N/A'}")
            col1.write(f"**LinkedIn:** {record.resume.linkedin or 'N/A'}")
            col2.write(f"**Fit Score:** {record.score.fit_score}")
            col2.write(f"**Excellence Score:** {record.score.excellence_score}")
            col2.write(f"**Flags:** {', '.join(record.score.breakdown.flags) or 'None'}")

            st.write("**Fit Breakdown**")
            for key, component in record.score.breakdown.fit.items():
                st.write(f"- {key.replace('_', ' ').title()}: {component.score} — {component.rationale}")

            st.write("**Excellence Breakdown**")
            for key, component in record.score.breakdown.excellence.items():
                st.write(f"- {key.replace('_', ' ').title()}: {component.score} — {component.rationale}")

            st.write("**Achievements**")
            st.write("\n".join(f"- {item}" for item in record.resume.achievements) or "_None captured_")

            col_actions = st.columns(3)
            status_options = ["active", "advanced", "rejected", "withdrawn"]
            current_index = status_options.index(record.status) if record.status in status_options else 0
            new_status = col_actions[0].selectbox(
                "Update status",
                options=status_options,
                index=current_index,
                key=f"status_{record.candidate_id}",
            )
            if col_actions[0].button("Apply status", key=f"apply_status_{record.candidate_id}"):
                storage.update_candidate_status(record.candidate_id, new_status)
                st.experimental_rerun()

            if col_actions[1].button("Delete candidate", key=f"delete_{record.candidate_id}"):
                storage.delete_candidate(record.candidate_id)
                st.warning("Candidate removed.")
                st.experimental_rerun()

            if col_actions[2].button("Rescore candidate", key=f"rescore_{record.candidate_id}"):
                updated_score = score_candidate(job, record.resume, job.scoring_config)
                storage.update_candidate_score(record.candidate_id, updated_score)
                st.success("Candidate rescored.")
                st.experimental_rerun()


def main() -> None:
    st.set_page_config(
        page_title="Automated Applicant Scoring & Ranking",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    storage = get_storage()

    if "selected_job_id" not in st.session_state:
        st.session_state["selected_job_id"] = None
    if "show_job_form" not in st.session_state:
        st.session_state["show_job_form"] = False

    st.sidebar.title("Job Requisitions")
    jobs = storage.list_jobs()

    display_options = [
        f"{record.features.title} ({record.created_at.strftime('%Y-%m-%d')})"
        for record in jobs
    ]
    job_ids = [record.job_id for record in jobs]

    selected_option = None
    if job_ids:
        selected_option = st.sidebar.selectbox(
            "Select job",
            options=list(range(len(job_ids))),
            format_func=lambda idx: display_options[idx],
        )
        st.session_state["selected_job_id"] = job_ids[selected_option]

    if st.sidebar.button("+ Create new job"):
        st.session_state["show_job_form"] = True

    if st.session_state["show_job_form"]:
        new_job_id = render_job_creation(storage)
        if new_job_id:
            st.session_state["selected_job_id"] = new_job_id
            st.session_state["show_job_form"] = False
            st.experimental_rerun()
        return

    selected_job_id = st.session_state.get("selected_job_id")
    if not selected_job_id:
        st.info("Select an existing job or create a new one to begin.")
        return

    job_record = storage.get_job(selected_job_id)
    if not job_record:
        st.warning("Selected job was not found. Please refresh.")
        return

    job_features = job_record.features
    job_features = render_job_edit(storage, selected_job_id, job_features)
    render_job_summary(job_features)

    st.markdown("---")
    render_resume_ingest(storage, selected_job_id, job_features)

    st.markdown("---")
    render_candidate_dashboard(storage, selected_job_id, job_features)


if __name__ == "__main__":
    main()

