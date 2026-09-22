# Naukri Job Matcher

Fetch recent Naukri job postings, compare them with a resume using an Ollama chat model, and export matching jobs to Excel.

## Features

- Searches Naukri for the configured keyword and experience level.
- Fetches jobs from the Naukri search API.
- Extracts resume text from `data/karthick_resume_v02.pdf`.
- Scores jobs with the configured Ollama model.
- Keeps jobs with an ATS score of 70 or higher.
- Exports serial number, job ID, title, company details, ATS score, ATS reason, and clickable job links.
- Saves default Excel files in `exportedData/`.
- Captures Naukri application questionnaires, answers known profile questions, and asks for unknown mandatory answers.
- Stores the complete apply payload, questionnaire, answers, and outcome in MongoDB.
- Uses the resume and previously entered answers as Chroma context, asks Ollama for a batched answer set, and sends uncertain questions to the terminal with their options.

## Requirements

- Python 3.10 or newer
- Brave browser at `/usr/bin/brave`
- An Ollama-compatible model available to `langchain-ollama`
- A Naukri session that allows the search page to load
- MongoDB, local or remote, for apply workflow history
- Chroma and Ollama embedding/generation models

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install Playwright browser dependencies if needed:

```bash
playwright install
```

The fetcher currently launches Brave directly. If Brave is installed elsewhere, update the executable path in `root/jobFetcher.py`.

## Configuration

Update the global values in `config.py`:

- `G_SEARCH_KEY`: Naukri search keyword
- `G_USER_EXPERIENCE`: required experience
- `G_JOB_AGE_DAYS`: job age filter
- `G_MODEL`: Ollama model used for ATS scoring
- `G_MAX_PAGES`: maximum pages to fetch
- `G_CUTOFF_TIME_IN_MINUTES`: maximum job age in minutes

Set these optional environment variables in `.env`:

```text
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE=naukri_auto_apply
MONGO_COLLECTION=apply_workflows
EXPERIENCE_GENERATIVE_AI=1
EXPERIENCE_MACHINE_LEARNING=1
EXPERIENCE_PYTHON=3.6
NOTICE_PERIOD=3 Months
```

For answers that cannot be inferred, use `AUTO_APPLY_ANSWERS` as JSON keyed by questionnaire `category` or `questionId`. Mandatory values still prompt in the terminal when missing.

Place the resume at:

```text
data/karthick_resume_v02.pdf
```

## Run

From the project root:

```bash
python app.py
```

The generated workbook is saved to `exportedData/` with a timestamped filename.

## Project Structure

```text
.
├── app.py
├── config.py
├── data/
│   └── karthick_resume_v02.pdf
├── exportedData/
├── requirements.txt
└── root/
    ├── jobExporter.py
    ├── jobFetcher.py
    └── resumeMatcher.py
```

## Notes

The Naukri API and request headers used by this project are internal and may change. Run the project responsibly and comply with Naukri's terms of service.
