import time

import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from config import (
    G_CUTOFF_TIME_IN_MINUTES,
    G_JOB_AGE_DAYS,
    G_MAX_PAGES,
    G_MAX_RETRIES_PER_PAGE,
    G_NAKURI_API_URL,
    G_SEARCH_KEY,
    G_SEARCH_PAGE_URL,
    G_USER_EXPERIENCE,
)


session = requests.Session()


def getDynamicNkparam():
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, executable_path="/usr/bin/brave")
        page = browser.new_page()

        with page.expect_request(lambda r: "jobapi/v3/search" in r.url) as req:
            page.goto(G_SEARCH_PAGE_URL)
        nkparam = str(req.value.headers.get("nkparam"))
        browser.close()
        return nkparam


def getHeaders(nkparam: str):
    return {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "appid": "109",
        "clientid": "d3skt0p",
        "content-type": "application/json",
        "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
        "nkparam": nkparam,
        "systemid": "karthickdev",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
    }


def buildParams(page_no, search_key=G_SEARCH_KEY):
    params = {
        "noOfResults": 100,
        "urlType": "search_by_key_loc",
        "searchType": "adv",
        "sort": "f",
        "jobAge": G_JOB_AGE_DAYS,
        "location": "india",
        "pageNo": page_no,
        "experience": G_USER_EXPERIENCE,
        "nignbevent_src": "jobsearchDeskGNB",
        "seoKey": "jobs-in-india",
        "src": "jobsearchDesk",
        "latLong": "",
    }
    if search_key:
        params["seoKey"] = f"{search_key}-jobs-in-india"
        params["keyword"] = search_key
        params["k"] = search_key
    return params


KEEP_FIELDS = [
    "title", "jobId", "companyName", "tagsAndSkills", "companyId", "placeholders",
    "jdURL", "jobDescription", "createdDate", "salaryDetail",
    "experienceText", "minimumExperience", "maximumExperience",
    "companyApplyJob", "companyApplyUrl", "applyRedirectUrl",
    "walkinJob", "todaysJob", "questionnaireIdPresent",
]


def projectFields(jobs, fields=KEEP_FIELDS):
    return [{key: job.get(key) for key in fields} for job in jobs]


def filterByTime(allJobs):
    cutoff_ms = int((time.time() - G_CUTOFF_TIME_IN_MINUTES * 60) * 1000)
    return projectFields(
        [job for job in allJobs if job.get("createdDate", 0) >= cutoff_ms]
    )


def fetch_jobs(search_key=G_SEARCH_KEY):
    all_jobs = []
    nkparam = getDynamicNkparam()

    for page_no in range(1, G_MAX_PAGES + 1):
        params = buildParams(page_no, search_key)
        data = None
        success = False

        for attempt in range(1, G_MAX_RETRIES_PER_PAGE + 1):
            headers = getHeaders(nkparam)
            response = session.get(
                G_NAKURI_API_URL, params=params, headers=headers, timeout=30
            )
            print(f"Page {page_no}, attempt {attempt}: status {response.status_code}")

            try:
                data = response.json()
            except ValueError:
                print(f"Page {page_no}, attempt {attempt}: non-JSON response, retrying")
                print(f"Raw body (first 500 chars): {response.text[:500]}")
                print(f"Content-Type: {response.headers.get('Content-Type')}")
                data = None
                nkparam = getDynamicNkparam()
                continue

            if response.ok:
                success = True
                break

            print(f"Bad response: {data}")
            if data and data.get("statusCode") == 400:
                break
            nkparam = getDynamicNkparam()

        if not success:
            print(
                f"Giving up on page {page_no} after {G_MAX_RETRIES_PER_PAGE} attempts."
            )
            break

        job_details = data.get("jobDetails", []) if data else []
        if not job_details:
            print("No more jobs returned - stopping.")
            break

        all_jobs.extend(job_details)

    return filterByTime(all_jobs)
