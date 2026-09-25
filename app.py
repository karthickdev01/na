from datetime import datetime
from pathlib import Path
import shutil
import threading
import time

from flask import Flask, jsonify, request

from root.autoApply import GetBrowserPage, WaitUntilBrowserClosed, initJobAutoApply
from root.jobExporter import exportJobs
from root.jobFetcher import fetch_jobs
from root.resumeMatcher import filterMatchedJobs

app = Flask(__name__)


@app.get("/api/resume/update")
def updateLatestResume():
    BrowserSession = GetBrowserPage(True)
    BrowserPage = BrowserSession["Page"]

    resume_path = Path("data/resume.pdf")
    today = datetime.now().strftime("%Y-%m-%d")
    daily_resume_path = resume_path.parent / f"Karthick-Resume-{today}.pdf"
    shutil.copy2(resume_path, daily_resume_path)

    BrowserPage.goto(
        "https://www.naukri.com/mnjuser/profile",
        wait_until="domcontentloaded",
        timeout=60000,
    )

    time.sleep(3)
    delete_icon = BrowserPage.locator('i[data-title="delete-resume"]')
    if delete_icon.is_visible():
        delete_icon.click()
        BrowserPage.locator('button.btn-dark-ot:has-text("Delete"):visible').click()
        BrowserPage.locator(".confirmationBox", has_text="resume").wait_for(
            state="hidden", timeout=15000
        )
    time.sleep(3)

    file_input = BrowserPage.locator("#attachCV")
    file_input.wait_for(state="attached", timeout=30000)
    file_input.set_input_files(
        str(daily_resume_path.resolve()), timeout=30000
    )  # this alone fires change/upload

    BrowserPage.locator(".resume-name-inline").wait_for(state="visible", timeout=60000)
    daily_resume_path.unlink(missing_ok=True)
    BrowserPage.context.browser.close()

    result = {
        "success": True,
        "message": "Resume updated successfully",
        "file": str(daily_resume_path),
    }

    return result


@app.get("/api/view")
def ViewBrowser():
    BrowserSession = GetBrowserPage(True)
    BrowserPage = BrowserSession["Page"]
    BrowserResponse = {
        "status": "browser_open",
        "url": BrowserPage.url,
        "message": "Browser remains open until you close it manually.",
    }
    time.sleep(180)
    WaitUntilBrowserClosed()
    return jsonify(
        {
            **BrowserResponse,
            "status": "browser_closed",
        }
    )


@app.get("/api/apply")
@app.get("/api/apply/<search_key>")
def ApplyJobs(search_key=None):
    try:
        MatchedJobs = filterMatchedJobs(fetch_jobs(search_key))
        if (len(MatchedJobs)) > 0:
            exportJobs(MatchedJobs)
        Results = initJobAutoApply(MatchedJobs)
        return jsonify(
            {"status": "completed", "search_key": search_key, "results": Results}
        )
    except Exception as Error:
        return jsonify({"status": "error", "error": str(Error)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
