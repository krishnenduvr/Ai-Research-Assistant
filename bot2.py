import os
import tempfile

import docx
import PyPDF2
import requests
from gtts import gTTS
from gtts.lang import tts_langs
from langdetect import LangDetectException, detect #type: ignore


SUMMARY_PROMPT = """
You are a helpful document summarizer.
Summarize the user's text clearly, accurately, and briefly.
Use simple language and keep the important points.
Write the summary in the same language as the user's text.
"""

CHAT_PROMPT = """
You are a helpful AI assistant.
Reply clearly and naturally.
Always reply in the same language the user uses.
"""


def load_api_config():
    api_key = os.getenv("OLLAMA_API_KEY")
    base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")

    if not api_key:
        try:
            from api import OLLAMA_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL

            api_key = OLLAMA_API_KEY
            base_url = OLLAMA_BASE_URL
            model = OLLAMA_MODEL
        except ImportError:
            pass

    return api_key, base_url.rstrip("/") + "/api/chat", model


API_KEY, CHAT_URL, MODEL = load_api_config()


def extract_text_from_pdf(file_path):
    reader = PyPDF2.PdfReader(file_path)
    text = ""

    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"

    return text.strip()


def extract_text_from_docx(file_path):
    document = docx.Document(file_path)
    text = ""

    for paragraph in document.paragraphs:
        text += paragraph.text + "\n"

    return text.strip()


def extract_text_from_txt(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read().strip()


def get_input_text(user_input):
    if not os.path.exists(user_input):
        return user_input

    extension = os.path.splitext(user_input)[1].lower()

    if extension == ".pdf":
        return extract_text_from_pdf(user_input)
    if extension == ".docx":
        return extract_text_from_docx(user_input)
    if extension in [".txt", ".md", ".csv"]:
        return extract_text_from_txt(user_input)

    return ""


def ask_api(text, system_prompt):
    if not API_KEY:
        return "Missing OLLAMA_API_KEY. Add it as an environment variable or keep it in local api.py."

    response = requests.post(
        CHAT_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": text},
            ],
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def summarize_text(text):
    text = text.strip()

    if not text:
        return "No text found to summarize."

    chunks = [text[i:i + 12000] for i in range(0, len(text), 12000)]
    summaries = []

    for chunk in chunks[:5]:
        summaries.append(ask_api(chunk, SUMMARY_PROMPT))

    if len(summaries) == 1:
        return summaries[0]

    combined_summary = "\n\n".join(summaries)
    return ask_api("Create one final short summary from these summaries:\n\n" + combined_summary, SUMMARY_PROMPT)


def chat_with_bot(message):
    return ask_api(message, CHAT_PROMPT)


def detect_voice_language(text):
    try:
        language = detect(text)
    except LangDetectException:
        language = "en"

    if language == "zh-cn":
        language = "zh-CN"
    elif language == "zh-tw":
        language = "zh-TW"

    if language not in tts_langs():
        language = "en"

    return language


def text_to_speech(text):
    language = detect_voice_language(text)
    audio = gTTS(text=text, lang=language)
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    audio.save(temp_audio.name)
    return temp_audio.name


def main():
    print("Chat + Document Summarizer with Audio")
    print("Enter a PDF, DOCX, TXT, MD, or CSV file path to summarize it.")
    print("Use 'sum: your text' to summarize pasted text.")
    print("Type normally to chat with the bot.")
    print("Type 'exit' to stop.\n")

    while True:
        user_input = input("You: ").strip().strip('"')

        if user_input.lower() in ["exit", "quit"]:
            break

        if not user_input:
            continue

        try:
            if os.path.exists(user_input):
                text = get_input_text(user_input)

                if not text:
                    print("Could not read text from that file.\n")
                    continue

                print("\nSummarizing document...")
                answer = summarize_text(text)
                label = "Summary"
            elif user_input.lower().startswith("sum:"):
                text = user_input[4:].strip()

                if not text:
                    print("Please type text after 'sum:'.\n")
                    continue

                print("\nSummarizing text...")
                answer = summarize_text(text)
                label = "Summary"
            else:
                print("\nThinking...")
                answer = chat_with_bot(user_input)
                label = "Bot"

            print(f"\n{label}:\n{answer}")
            audio_path = text_to_speech(answer)
            print("\nAudio saved at:", audio_path, "\n")
        except Exception as error:
            print("\nError:", error, "\n")


if __name__ == "__main__":
    main()
