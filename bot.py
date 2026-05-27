import os

import requests


def load_config():
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


API_KEY, BASE_URL, MODEL = load_config()
SYSTEM_PROMPT = "You are a helpful AI assistant."


def ask_bot(question):
    if not API_KEY:
        return "Missing OLLAMA_API_KEY. Set it as an environment variable."

    response = requests.post(
        BASE_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


print("Chatbot is ready! Type 'exit' to stop.")

while True:
    question = input("You: ").strip()

    if question.lower() == "exit":
        print("Bot: Goodbye!")
        break

    if not question:
        continue

    try:
        answer = ask_bot(question)
    except Exception as error:
        answer = f"Error: {error}"

    print("Bot:", answer)
