import os
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT_DIR, ".env"))
G_DATA_PATH = os.path.abspath(os.path.join(ROOT_DIR, ".", "data"))
G_EXPORTED_DATA_PATH = os.path.abspath(os.path.join(ROOT_DIR, ".", "exportedData"))

# G_MODEL = os.getenv("G_MODEL", "gpt-oss:120b-cloud")
G_MODEL = "gpt-oss:120b-cloud"
G_SEARCH_KEY = "full stack developer"
G_USER_EXPERIENCE = 3
G_JOB_AGE_DAYS = 1
G_CUTOFF_TIME_IN_MINUTES = 0.5 * 60
G_CUTOFF_SCORE = 70

G_MAX_PAGES = 100
G_MAX_RETRIES_PER_PAGE = 3

G_NAKURI_WEB_URL = "https://www.naukri.com"
G_NAKURI_LOGIN_URL = "https://www.naukri.com/nlogin/login"
G_NAKURI_API_URL = "https://www.naukri.com/jobapi/v3/search"
G_SEARCH_PAGE_URL = "https://www.naukri.com/jobs-in-india"