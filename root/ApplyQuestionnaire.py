import json
import os
import time
from datetime import datetime, timezone

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import ChatOllama, OllamaEmbeddings
from pymongo import MongoClient

from config import G_DATA_PATH, G_MODEL

DrawerSelector = "div.chatbot_Drawer:visible"
AcceptedCities = ["Pune", "Hyderabad", "Kochi", "Bangalore", "Chennai"]


def GetVectorStore():
    ChromaPath = os.path.abspath(os.path.join(os.path.dirname(G_DATA_PATH), "chroma"))
    Embeddings = OllamaEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    )
    VectorStore = Chroma(
        collection_name="resume_answers",
        persist_directory=ChromaPath,
        embedding_function=Embeddings,
    )
    return VectorStore


def GetCurrentQuestion(Drawer):
    QuestionMessages = Drawer.locator(".botMsg:visible")
    if QuestionMessages.count() == 0:
        return ""
    return QuestionMessages.last.inner_text().strip()


def StoreAnswer(VectorStore, Question, Answer, Source):
    ExistingAnswers = VectorStore.get(
        where={
            "$and": [
                {"source": "question_answer"},
                {"question": Question},
            ]
        },
        include=["metadatas"],
    )
    if ExistingAnswers.get("ids"):
        return

    VectorStore.add_documents(
        [
            Document(
                page_content=f"Question: {Question}\nAnswer: {Answer}",
                metadata={
                    "source": "question_answer",
                    "question": Question,
                    "answerSource": Source,
                },
            )
        ]
    )


def GetAnswer(Question, VectorStore, LanguageModel, Drawer):
    if "relocat" in Question.lower() or "city" in Question.lower():
        Options = Drawer.locator("label:visible, [role='option']:visible")
        OptionTexts = [
            " ".join(Options.nth(Index).inner_text().lower().split())
            for Index in range(Options.count())
        ]
        AnywhereOption = next(
            (
                Options.nth(Index).inner_text().strip()
                for Index, OptionText in enumerate(OptionTexts)
                if "anywhere in india" in OptionText
                or "any location in india" in OptionText
            ),
            None,
        )
        Answer = AnywhereOption or AcceptedCities
        StoreAnswer(VectorStore, Question, json.dumps(Answer), "profile")
        return Answer

    ContextDocuments = VectorStore.similarity_search(Question, k=5)
    Context = "\n\n".join(
        ContextDocument.page_content for ContextDocument in ContextDocuments
    )
    Prompt = (
        "Answer this job application question using only the context. "
        'Return JSON only: {"answer": "text", "confidence": 0.0}. '
        "Return UNKNOWN when the context is insufficient.\n"
        f"Context:\n{Context}\nQuestion:\n{Question}"
    )
    Answer = ""
    try:
        ModelText = LanguageModel.invoke(Prompt).content.strip()
        ModelText = ModelText.removeprefix("```json").removesuffix("```").strip()
        ModelAnswer = json.loads(ModelText)
        if float(ModelAnswer.get("confidence", 0)) >= 0.8:
            Answer = str(ModelAnswer.get("answer", "")).strip()
    except Exception:
        pass

    if Answer and Answer.upper() != "UNKNOWN":
        StoreAnswer(VectorStore, Question, Answer, "llm")
        return Answer

    print(f"\nQuestion: {Question}")
    Options = Drawer.locator("label:visible, [role='option']:visible")
    for OptionIndex in range(Options.count()):
        print(f"{OptionIndex}: {Options.nth(OptionIndex).inner_text().strip()}")
    Answer = input("Enter answer: ").strip()
    if Answer:
        StoreAnswer(VectorStore, Question, Answer, "terminal")
    return Answer


def FillCurrentAnswer(Drawer, Answer):
    Answers = Answer if isinstance(Answer, (list, tuple, set)) else [Answer]
    NormalizedAnswers = [" ".join(str(Item).lower().split()) for Item in Answers]

    ChoiceInputs = Drawer.locator(
        "input[type='checkbox'], input[type='radio']"
    )
    if ChoiceInputs.count() > 0:
        FoundAny = False
        for ChoiceIndex in range(ChoiceInputs.count()):
            ChoiceInput = ChoiceInputs.nth(ChoiceIndex)
            ChoiceId = ChoiceInput.get_attribute("id")
            ChoiceLabel = (
                Drawer.locator(f"label[for='{ChoiceId}']").first
                if ChoiceId
                else ChoiceInput.locator("xpath=ancestor::label[1]")
            )
            ChoiceText = (
                " ".join(ChoiceLabel.inner_text().lower().split())
                if ChoiceLabel.count() > 0
                else ""
            )
            IsMatch = any(
                Value == ChoiceText
                or Value in ChoiceText
                or ChoiceText in Value
                or (Value == "bangalore" and "bengaluru" in ChoiceText)
                for Value in NormalizedAnswers
            )
            if IsMatch:
                if ChoiceLabel.count() > 0 and ChoiceLabel.is_visible():
                    ChoiceLabel.click(force=True)
                    FoundAny = True
                elif not ChoiceInput.is_checked():
                    try:
                        ChoiceInput.check(force=True)
                        FoundAny = True
                    except Exception:
                        MatchingText = Drawer.get_by_text(
                            str(Answers[0]), exact=False
                        ).last
                        if MatchingText.count() > 0 and MatchingText.is_visible():
                            MatchingText.click(force=True)
                            FoundAny = True
        if FoundAny:
            time.sleep(1)
        return FoundAny

    CustomOption = Drawer.locator(
        "[role='option']:visible, [role='radio']:visible, [role='checkbox']:visible"
    )
    for OptionIndex in range(CustomOption.count()):
        Option = CustomOption.nth(OptionIndex)
        OptionText = " ".join(Option.inner_text().lower().split())
        if any(Value == OptionText or Value in OptionText for Value in NormalizedAnswers):
            Option.click()
            time.sleep(1)
            return True

    AnswerField = Drawer.locator(
        "input:visible, textarea:visible, select:visible, "
        "[role='textbox']:visible, [role='combobox']:visible, "
        "[contenteditable='true']:visible"
    ).last

    if AnswerField.count() == 0:
        return False

    TagName = AnswerField.evaluate("el => el.tagName.toLowerCase()")

    InputType = AnswerField.get_attribute("type") or ""
    IsContentEditable = AnswerField.get_attribute("contenteditable")

    if TagName == "select":
        try:
            AnswerField.select_option(label=str(Answer))
        except Exception:
            AnswerField.select_option(value=str(Answer))
    elif InputType == "file":
        return False
    elif IsContentEditable == "true":
        AnswerField.click()
        AnswerField.fill(str(Answer))
    else:
        AnswerField.fill(str(Answer))

    time.sleep(1)
    return True


def SaveCurrentAnswer(Page, Drawer):
    SaveButton = Drawer.get_by_role("button", name="Save", exact=True).last
    if SaveButton.count() == 0:
        SaveButton = Page.get_by_text("Save", exact=True).last
    if SaveButton.count() == 0 or not SaveButton.is_visible():
        return False
    SaveButton.click()
    Page.wait_for_timeout(3000)
    return True


def SaveApplication(Page, AnswerRecords):
    try:
        MongoClient(
            os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            serverSelectionTimeoutMS=3000,
        )[
            os.getenv("MONGO_DATABASE", "naukri_auto_apply")
        ][os.getenv("MONGO_COLLECTION", "apply_workflows")].insert_one(
            {
                "jobUrl": Page.url,
                "answers": AnswerRecords,
                "status": "applied",
                "createdAt": datetime.now(timezone.utc),
            }
        )
    except Exception as Error:
        print(f"MongoDB save skipped: {Error}")


def ProcessDrawerQuestions(Page):
    Drawer = Page.locator(DrawerSelector).first
    if Drawer.count() == 0:
        return True

    VectorStore = GetVectorStore()
    LanguageModel = ChatOllama(model=G_MODEL, temperature=0)
    AnswerRecords = []
    LastQuestion = ""

    while Drawer.count() > 0 and Drawer.is_visible():
        CurrentQuestion = GetCurrentQuestion(Drawer)
        if not CurrentQuestion:
            break
        if CurrentQuestion == LastQuestion:
            Page.wait_for_timeout(500)
            continue

        Answer = GetAnswer(CurrentQuestion, VectorStore, LanguageModel, Drawer)
        if not Answer or not FillCurrentAnswer(Drawer, Answer):
            return False
        if not SaveCurrentAnswer(Page, Drawer):
            return False

        AnswerRecords.append({"question": CurrentQuestion, "answer": Answer})
        LastQuestion = CurrentQuestion
        Drawer = Page.locator(DrawerSelector).first

    SaveApplication(Page, AnswerRecords)
    print("🚀 ~ ProcessDrawerQuestions ~ AnswerRecords:", AnswerRecords)
    return True
