from root.autoApply import _absolute_url, apply_job
from root.questionnaire import questionnaire_from_payload, resolve_answers, select_option


class FakePage:
    def __init__(self):
        self.visited = []
        self.clicked = []

    def goto(self, url, wait_until=None, timeout=None):
        self.visited.append(url)

    def locator(self, selector):
        class FakeLocator:
            def __init__(self, page, selector):
                self.page = page
                self.selector = selector

            def click(self):
                self.page.clicked.append(self.selector)
                return self

            def is_visible(self):
                return True

            def first(self):
                return self

            def nth(self, index):
                return self

            def fill(self, value):
                return self

            def get_by_role(self, *args, **kwargs):
                return self

            def inner_text(self):
                return "Apply"

        return FakeLocator(self, selector)

    def wait_for_timeout(self, ms):
        return None

    @property
    def url(self):
        return self.visited[-1] if self.visited else ""


def test_absolute_url_uses_naukri_base_for_relative_links():
    assert _absolute_url("/jobs/example") == "https://www.naukri.com/jobs/example"
    assert _absolute_url("") == ""


def test_apply_job_redirects_when_apply_button_is_missing():
    page = FakePage()
    job = {
        "jobId": "123",
        "jdURL": "/job-listings/abc",
        "applyRedirectUrl": "/redirect/next",
        "companyApplyUrl": "https://company.example/apply",
    }

    status = apply_job(page, job)

    assert status == "redirected"
    assert page.visited[-1] == "https://www.naukri.com/redirect/next"


def test_resolve_answers_uses_profile_and_asks_for_unknown_mandatory_answer():
    questions = [
        {
            "category": "EXPERIENCE_IN_7681",
            "questionName": "Python experience",
            "isMandatory": True,
        },
        {
            "category": "UNKNOWN_CATEGORY",
            "questionName": "Work authorization",
            "isMandatory": True,
        },
    ]

    answers = resolve_answers(questions, answer_provider=lambda _: "Yes", model=False)

    assert answers["EXPERIENCE_IN_7681"] == "3.6"
    assert answers["UNKNOWN_CATEGORY"] == "Yes"


def test_questionnaire_payload_and_list_option_are_supported():
    question = {
        "category": "JPSQ_20045",
        "answerOption": {"0": "15 Days or less", "3": "3 Months"},
    }
    payload = {"jobs": [{"questionnaire": [question]}]}

    assert questionnaire_from_payload(payload) == [question]
    assert select_option(question, "3 months") == "3 Months"
