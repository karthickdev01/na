import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from config import G_NAKURI_WEB_URL
from root.ApplyQuestionnaire import ProcessDrawerQuestions

ApplySession = {}


def GetBrowserPage(show=True):
    if ApplySession.get("Page") and not ApplySession["Page"].is_closed():
        return ApplySession

    UserDataDirectory = "/home/karthick/.config/BraveSoftware/Brave-Naukri-Bot"
    PlaywrightManager = Stealth().use_sync(sync_playwright())
    Playwright = PlaywrightManager.start()
    BrowserContext = Playwright.chromium.launch_persistent_context(
        UserDataDirectory,
        headless=False,
        executable_path="/usr/bin/brave",
        args=["--profile-directory=Default"],
    )
    Pages = BrowserContext.pages
    Page = Pages[0] if Pages else BrowserContext.new_page()
    for OtherPage in Pages[1:]:
        OtherPage.close()

    if show:
        Page.goto(G_NAKURI_WEB_URL, wait_until="domcontentloaded", timeout=60000)

    ApplySession.update({
        "PlaywrightManager": PlaywrightManager,
        "Playwright": Playwright,
        "BrowserContext": BrowserContext,
        "Page": Page,
    })
    return ApplySession


def WaitUntilBrowserClosed():
    if not ApplySession.get("Page"):
        return

    Page = ApplySession["Page"]
    try:
        if not Page.is_closed():
            Page.wait_for_event("close")
    finally:
        BrowserContext = ApplySession.get("BrowserContext")
        PlaywrightManager = ApplySession.get("PlaywrightManager")
        if BrowserContext:
            BrowserContext.close()
        if PlaywrightManager:
            PlaywrightManager.__exit__(None, None, None)
        ApplySession.clear()


def clickApply(page):
    time.sleep(1)
    ApplyButton = page.get_by_role("button", name="Apply", exact=True)
    if ApplyButton.count() == 0:
        return False

    ApplyButton.first.click()
    page.wait_for_timeout(5000)
    return ProcessDrawerQuestions(page)


def absoluteUrl(value):
    if not value:
        return ""
    value = str(value).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return urljoin(f"{G_NAKURI_WEB_URL}/", value)


def autoJobApply(page, job):
    JobId = str(job.get("jobId", "unknown"))
    JobUrl = absoluteUrl(job.get("jdURL") or job.get("jobUrl") or job.get("url"))

    if not JobUrl:
        print(f"Job {JobId}: job page error: Job URL not found")
        return "notFound"

    page.goto(JobUrl, wait_until="domcontentloaded", timeout=60000)
    if not clickApply(page):
        return "apply_not_completed"
    print(f"Job {JobId}: apply button clicked")
    return "applied"


def initJobAutoApply(jobs):
    Page = GetBrowserPage()["Page"]
    Results = []
    for Job in jobs or []:
        try:
            Status = autoJobApply(Page, Job)
        except Exception as Error:
            Status = "error"
            print(f"Job {Job.get('jobId', 'unknown')}: {Error}")
        Results.append({"jobId": Job.get("jobId"), "status": Status})

    Page.context.browser.close()
    return Results
