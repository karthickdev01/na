from datetime import datetime, time, timedelta, timezone
import os

from pymongo import MongoClient


DailyApplyMaximum = 40


def GetTodayRange():
    Today = datetime.now(timezone.utc).date()
    StartOfDay = datetime.combine(Today, time.min, tzinfo=timezone.utc)
    return StartOfDay, StartOfDay + timedelta(days=1)


def GetTodayAppliedCount():
    MongoUri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MongoDatabase = os.getenv("MONGO_DATABASE", "naukri_auto_apply")
    MongoCollection = os.getenv("MONGO_COLLECTION", "apply_workflows")
    StartOfDay, StartOfNextDay = GetTodayRange()

    MongoClientInstance = MongoClient(MongoUri, serverSelectionTimeoutMS=3000)
    try:
        return MongoClientInstance[MongoDatabase][MongoCollection].count_documents(
            {
                "status": "applied",
                "createdAt": {
                    "$gte": StartOfDay,
                    "$lt": StartOfNextDay,
                },
            }
        )
    finally:
        MongoClientInstance.close()


def GetRemainingApplySlots():
    return max(DailyApplyMaximum - GetTodayAppliedCount(), 0)


def IsDailyApplyLimitExceeded():
    return GetTodayAppliedCount() >= DailyApplyMaximum
