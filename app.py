from flask import Flask, jsonify, request

from root.autoApply import GetBrowserPage, WaitUntilBrowserClosed, initJobAutoApply
from root.DailyApplyLimit import (
    GetRemainingApplySlots,
    GetTodayAppliedCount,
    IsDailyApplyLimitExceeded,
)
from root.jobExporter import exportJobs
from root.jobFetcher import fetch_jobs
from root.resumeMatcher import filterMatchedJobs

app = Flask(__name__)


@app.get("/api/view")
def ViewBrowser():
    BrowserSession = GetBrowserPage(True)
    BrowserPage = BrowserSession["Page"]
    BrowserResponse = {
        "status": "browser_open",
        "url": BrowserPage.url,
        "message": "Browser remains open until you close it manually.",
    }
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
        if IsDailyApplyLimitExceeded():
            return (
                jsonify(
                    {
                        "status": "daily_limit_exceeded",
                        "limit": 40,
                        "appliedToday": GetTodayAppliedCount(),
                    }
                ),
                429,
            )

        MatchedJobs = filterMatchedJobs(fetch_jobs(search_key))
        MatchedJobs = MatchedJobs[: GetRemainingApplySlots()]
        exportJobs(MatchedJobs)
        Results = initJobAutoApply(MatchedJobs)
        return jsonify(
            {"status": "completed", "search_key": search_key, "results": Results}
        )
    except Exception as Error:
        return jsonify({"status": "error", "error": str(Error)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
