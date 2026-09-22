import json
import re

import pdfplumber
from langchain_ollama import ChatOllama

from config import G_CUTOFF_SCORE, G_DATA_PATH, G_MODEL

def extract_resume_text(pdf_path=f"{G_DATA_PATH}/karthick_resume_v02.pdf"):
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return "\n".join(text)


def clean_job_description(html_desc: str) -> str:
    return re.sub(r"<[^>]+>", " ", html_desc).strip()


def build_batch_prompt(resume_text: str, job_batch: list) -> str:
    jobs_block = ""
    for i, job in enumerate(job_batch, start=1):
        desc = clean_job_description(job.get("jobDescription", ""))
        jobs_block += (
            f"\n--- JOB {i} (jobId: {job.get('jobId')}) ---"
            f"\nTitle: {job.get('title')}\nDescription: {desc}\n"
        )

    return f"""
        You are an ATS (Applicant Tracking System) scoring engine.

        RESUME:
        {resume_text}

        Below are {len(job_batch)} job postings. For EACH job, score how well the resume matches the job description on a scale of 0-100, based on skills overlap, experience level, and role relevance.

        {jobs_block}

        Respond ONLY with a valid JSON array, no markdown, no explanation, in this exact format:
        [
        {{"jobId": "210926028982", "atsScore": 32, "reason": "short one-line reason"}},
        ...
        ]
        The array must contain exactly {len(job_batch)} objects, one per job above, matching jobId exactly.
    """


def filterMatchedJobs(jobs: list, batch_size: int = 10) -> list:
    resume_text = extract_resume_text()
    model = ChatOllama(model=G_MODEL)

    job_by_id = {str(job["jobId"]): job for job in jobs}
    scored_jobs = []

    for start in range(0, len(jobs), batch_size):
        batch = jobs[start : start + batch_size]
        prompt = build_batch_prompt(resume_text, batch)

        response = model.invoke(prompt)
        raw = response.content.strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())

        try:
            results = json.loads(raw)
        except json.JSONDecodeError:
            print(
                f"Batch {start // batch_size + 1}: failed to parse JSON, skipping. "
                f"Raw: {raw[:200]}"
            )
            for job in batch:
                job["atsScore"] = None
                job["atsReason"] = "parse_error"
                scored_jobs.append(job)
            continue

        for result in results:
            job_id = str(result.get("jobId"))
            job = job_by_id.get(job_id)
            raw_score = result.get("atsScore")
            try:
                ats_score = float(raw_score)
            except (TypeError, ValueError):
                ats_score = None

            if job and ats_score is not None and ats_score >= G_CUTOFF_SCORE:
                print("Matched job:", job_id, result)
                job["atsScore"] = ats_score
                job["atsReason"] = result.get("reason")
                scored_jobs.append(job)

        print(f"Batch {start // batch_size + 1} done: {len(batch)} jobs scored")

    return scored_jobs
