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
        return "", []

    QuestionText = QuestionMessages.last.inner_text().strip()

    Options = []

    ChoiceInputs = Drawer.locator("input[type='checkbox']:visible, input[type='radio']:visible")
    if ChoiceInputs.count() > 0:
        for ChoiceIndex in range(ChoiceInputs.count()):
            ChoiceInput = ChoiceInputs.nth(ChoiceIndex)
            ChoiceId = ChoiceInput.get_attribute("id")
            ChoiceLabel = (
                Drawer.locator(f"label[for='{ChoiceId}']").first
                if ChoiceId
                else ChoiceInput.locator("xpath=ancestor::label[1]")
            )
            if ChoiceLabel.count() > 0:
                LabelText = " ".join(ChoiceLabel.inner_text().split()).strip()
                if LabelText:
                    Options.append(LabelText)
        return QuestionText, Options

    SelectField = Drawer.locator("select:visible")
    if SelectField.count() > 0:
        OptionElements = SelectField.first.locator("option")
        for OptionIndex in range(OptionElements.count()):
            OptionText = OptionElements.nth(OptionIndex).inner_text().strip()
            if OptionText:
                Options.append(OptionText)
        return QuestionText, Options

    return QuestionText, Options


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


def GetAnswer(Question, Options, VectorStore, LanguageModel, Drawer):
    ContextDocuments = VectorStore.similarity_search(Question, k=5)
    Context = "\n\n".join(
        ContextDocument.page_content for ContextDocument in ContextDocuments
    )

    OptionsBlock = ""
    if Options:
        OptionsBlock = (
            "This question has a fixed set of choices. Pick exactly one and return "
            "its text exactly as written below — do not paraphrase or invent a new option.\n"
            + "\n".join(f"- {Option}" for Option in Options)
            + "\n"
        )

    Prompt = (
        "Answer this job application question using only the context. "
        'Return JSON only: {"answer": "text", "confidence": 0.0}. '
        "Return UNKNOWN when the context is insufficient.\n"
        f"{OptionsBlock}"
        f"Context:\n{Context}\nQuestion:\n{Question}"
    )

    Answer = ""
    try:
        ModelText = LanguageModel.invoke(Prompt).content.strip()
        ModelText = ModelText.removeprefix("```json").removesuffix("```").strip()
        ModelAnswer = json.loads(ModelText)
        if float(ModelAnswer.get("confidence", 0)) >= 0.8:
            RawAnswer = str(ModelAnswer.get("answer", "")).strip()
            if Options:
                NormalizedOptions = {Option.strip().lower(): Option for Option in Options}
                Answer = NormalizedOptions.get(RawAnswer.strip().lower(), "")
            else:
                Answer = RawAnswer
    except Exception:
        pass

    if Answer and Answer.upper() != "UNKNOWN":
        StoreAnswer(VectorStore, Question, Answer, "llm")
        return Answer

    print(f"\nQuestion: {Question}")
    if Options:
        for OptionIndex, OptionText in enumerate(Options):
            print(f"{OptionIndex}: {OptionText}")
        RawInput = input("Enter option number (or type a custom answer): ").strip()
        if RawInput.isdigit() and 0 <= int(RawInput) < len(Options):
            Answer = Options[int(RawInput)]
        else:
            Answer = RawInput
    else:
        Answer = input("Enter answer: ").strip()

    if Answer:
        StoreAnswer(VectorStore, Question, Answer, "terminal")
    return Answer

def FillCurrentAnswer(Drawer, Answer):
    Answers = Answer if isinstance(Answer, (list, tuple, set)) else [Answer]
    NormalizedAnswers = [" ".join(str(Item).lower().split()) for Item in Answers]

    ChoiceInputs = Drawer.locator("input[type='checkbox'], input[type='radio']")
    if ChoiceInputs.count() > 0:
        ChoiceInput = Drawer.locator(f"input[type='radio'][id='{Answer}'], input[type='checkbox'][id='{Answer}']").first
        if ChoiceInput.count() == 0:
            return False
        ChoiceLabel = Drawer.locator(f"label[for='{Answer}']").first
        if ChoiceLabel.count() > 0:
            ChoiceLabel.click(force=True)
        else:
            ChoiceInput.dispatch_event("click")
        ChoiceInput.evaluate(
            "el => { el.checked = true; "
            "el.dispatchEvent(new Event('input', { bubbles: true })); "
            "el.dispatchEvent(new Event('change', { bubbles: true })); }"
        )
        time.sleep(3)
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

    time.sleep(3)
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
        CurrentQuestion, CurrentOptions = GetCurrentQuestion(Drawer)
        print("🚀 ~ ProcessDrawerQuestions ~ CurrentOptions:", CurrentOptions)
        print("🚀 ~ ProcessDrawerQuestions ~ CurrentQuestion:", CurrentQuestion)
        if not CurrentQuestion:
            break
        if CurrentQuestion == LastQuestion:
            Page.wait_for_timeout(500)
            continue

        Answer = GetAnswer(CurrentQuestion, CurrentOptions, VectorStore, LanguageModel, Drawer)
        print("🚀 ~ ProcessDrawerQuestions ~ Answer:", Answer)
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

        
