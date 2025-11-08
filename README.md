# SmartATS – Automated Applicant Scoring & Ranking

SmartATS helps recruiters keep up with high inbound applicant volumes by automating the heavy lifting: parsing job descriptions and resumes, extracting structured insights, and ranking candidates with transparent fit and excellence scores. The Streamlit dashboard provides a recruiter-friendly workflow that keeps human decision makers in control while surfacing the strongest matches first.

## Key Capabilities
- **Flexible JD intake** – upload machine-readable PDF/DOCX files or paste text, then review and edit extracted skills, responsibilities, and requirements.
- **Resume processing** – upload multiple resumes per job, with automatic parsing of skills, experience, education, achievements, and contact details.
- **Configurable scoring** – adjust fit (must-have skills, experience, domain, location) and excellence (education, career trajectory, achievements, skills depth) weights per job. The platform enforces a 70/30 final weight split by default.
- **Explainable rankings** – every candidate receives a detailed fit and excellence breakdown, with flags for missing must-haves and other risk signals.
- **Live dashboard** – view ranked candidates per job, update candidate status, rescore after configuration changes, or remove applicants as workflows progress.

## Project Structure
```
src/
  app.py                               # Streamlit application entry point
  automation_tool/
    __init__.py
    data_models.py                     # Pydantic schemas for jobs, resumes, scores
    domain_knowledge/skills_taxonomy.json
    file_ingest.py                     # PDF / DOCX ingestion helpers
    jd_parser.py                       # Job description parsing & feature extraction
    resume_parser.py                   # Resume parsing & normalization
    scoring.py                         # Fit & excellence scoring logic
    ranking_service.py                 # Ranking helpers + dataframe view
    storage.py                         # SQLite persistence layer
    text_utils.py                      # Tokenization, keyword extraction, heuristics
requirements.txt
README.md
```

The application persists data to `automation.db` in the project root, so recruiters can reopen the dashboard without losing prior work.

## Prerequisites
- Python 3.10+
- Virtual environment tool (e.g. `venv`, `conda`, or `pyenv`)

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Running the Dashboard
```bash
streamlit run src/app.py
```

The app launches in your browser (default: http://localhost:8501).

## Workflow Overview
1. **Create a job definition**
   - Click “Create new job”, upload a JD or paste text, and optionally enter structured overrides (must-have skills, responsibilities, certifications, etc.).
   - Review & adjust fit/excellence weights per job; saving triggers persistence and auto rescoring.
2. **Add candidates**
   - Within the job, upload one or more PDF/DOCX/TXT resumes. The system parses skills, experience, education, achievements, and contact info automatically.
3. **Review rankings**
   - Candidates are sorted by final score (70% fit, 30% excellence) with tie-breaks: must-have coverage → domain match → career trajectory → notable achievements.
   - Drill into any candidate to inspect the score breakdown, extracted achievements, and risk flags.
4. **Take action**
   - Update candidate status (active, advanced, rejected, withdrawn), rescore after manual edits, or delete records when candidates leave the pipeline.

## Scoring Model Highlights
- **Fit (0–100)**
  - Must-have skills (default 40 points): partial credit based on coverage; missing skills cap the overall fit score at 50.
  - Experience alignment (30 points): compares years of experience to JD minimums with partial credit.
  - Domain/industry (20 points): rewards overlaps with JD domain tags.
  - Location (10 points): favors matching locations, with partial credit for remote/hybrid roles.
- **Excellence (0–100)**
  - Education quality (25 points): recognizes advanced degrees and professional programs.
  - Career trajectory (25 points): infers progression through titles/responsibilities.
  - Achievements (25 points): detects quantified impact statements (%, $, growth metrics, etc.).
  - Skills depth (25 points): measures breadth of parsed skills.
- **Final score**: 70% fit + 30% excellence (per requirements). Recruiters can customise sub-component weights per job.

## Extending the Tool
- Add new skills, domains, or seniority markers by extending `skills_taxonomy.json`.
- Swap in alternative parsing strategies (e.g., embedding-based models) within `jd_parser.py` and `resume_parser.py`.
- Integrate with ATS or messaging tools by building on the storage layer (`storage.py`) or exposing APIs.

## Troubleshooting
- **Unsupported file types**: ensure resumes/JDs are machine-readable PDFs, DOCX, or TXT. Scans without text layers are not yet supported.
- **Weights sum check**: the UI normalizes component weights, but keeping totals near 100 helps interpret scores intuitively.
- **Database resets**: delete `automation.db` if you want to start fresh—new jobs/candidates will be created on next launch.

---
Built to keep recruiters in the loop while providing the automation they need to shortlist quickly and confidently.
