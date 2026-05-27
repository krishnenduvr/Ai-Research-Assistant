import os
from io import BytesIO

import docx
import PyPDF2

import requests
import streamlit as st
from gtts import gTTS
from gtts.lang import tts_langs
from langdetect import LangDetectException, detect #type: ignore

try:
    import speech_recognition as sr #type: ignore
except ImportError:
    sr = None


APP_NAME = "AI Research Agent"

CHAT_PROMPT = """
You are a professional AI research agent.
Answer clearly, accurately, and in the same language as the user.
When useful, structure the answer with concise points.
"""

SUMMARY_PROMPT = """
You are a professional AI research agent.
Summarize the uploaded research content clearly and accurately.
Keep the important points and write in the same language as the document or user.
"""


def get_secret(name, default=None):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


def load_api_config():
    api_key = get_secret("OLLAMA_API_KEY")
    base_url = get_secret("OLLAMA_BASE_URL", "https://ollama.com")
    model = get_secret("OLLAMA_MODEL", "gpt-oss:120b")

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


def apply_design():
    st.markdown(
        """
        <style>
        :root {
            --bg: #fff8fd;
            --panel: #ffffff;
            --ink: #20152f;
            --muted: #715f83;
            --line: #eadcf8;
            --brand: #7c3aed;
            --brand-dark: #5b21b6;
            --accent: #ec4899;
            --mint: #14b8a6;
            --sun: #f59e0b;
        }

        .stApp {
            background:
                radial-gradient(circle at 8% 0%, rgba(236, 72, 153, 0.18), transparent 28rem),
                radial-gradient(circle at 88% 14%, rgba(20, 184, 166, 0.14), transparent 26rem),
                linear-gradient(135deg, #fff8fd 0%, #f8f1ff 46%, #eefcff 100%);
            color: var(--ink);
        }

        [data-testid="stSidebar"] {
            display: none;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 1160px;
            padding-top: 1rem;
            padding-bottom: 2rem;
        }

        .top-nav {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.9rem 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            border: 1px solid rgba(124, 58, 237, 0.15);
            background: rgba(255, 255, 255, 0.76);
            box-shadow: 0 18px 50px rgba(91, 33, 182, 0.10);
            backdrop-filter: blur(18px);
        }

        .brand-lockup {
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }

        .brand-mark {
            display: grid;
            place-items: center;
            width: 2.6rem;
            height: 2.6rem;
            border-radius: 8px;
            color: white;
            font-weight: 800;
            background: linear-gradient(135deg, var(--brand), var(--accent));
            box-shadow: 0 12px 24px rgba(124, 58, 237, 0.26);
        }

        .brand-title {
            font-size: 1.05rem;
            font-weight: 780;
            color: var(--ink);
            line-height: 1.15;
        }

        .brand-subtitle {
            color: var(--muted);
            font-size: 0.82rem;
            margin-top: 0.1rem;
        }

        .nav-actions {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 0.65rem;
            color: var(--muted);
            font-size: 0.9rem;
        }

        .app-hero {
            padding: 1.45rem 1.6rem;
            border: 1px solid rgba(124, 58, 237, 0.14);
            background:
                linear-gradient(135deg, rgba(255, 255, 255, 0.94) 0%, rgba(253, 244, 255, 0.92) 54%, rgba(236, 253, 245, 0.88) 100%);
            border-radius: 8px;
            box-shadow: 0 22px 60px rgba(91, 33, 182, 0.10);
            margin-bottom: 1rem;
        }

        .app-title {
            font-size: 2rem;
            font-weight: 760;
            letter-spacing: 0;
            margin: 0;
            color: var(--ink);
        }

        .app-subtitle {
            color: var(--muted);
            margin-top: 0.35rem;
            font-size: 1rem;
            line-height: 1.5;
        }

        .chat-shell {
            min-height: 50vh;
            padding: 0.35rem 0 1rem;
        }

        .history-panel {
            padding: 1rem;
            margin: 0.75rem 0 1rem;
            border-radius: 8px;
            border: 1px solid rgba(124, 58, 237, 0.13);
            background: rgba(255, 255, 255, 0.74);
            box-shadow: 0 12px 32px rgba(91, 33, 182, 0.08);
        }

        .stChatMessage {
            border-radius: 8px;
            border: 1px solid rgba(124, 58, 237, 0.10);
            box-shadow: 0 10px 24px rgba(91, 33, 182, 0.05);
            background: rgba(255, 255, 255, 0.78);
        }

        .composer {
            padding: 1rem;
            margin-top: 0.75rem;
            border-radius: 8px;
            border: 1px solid rgba(124, 58, 237, 0.16);
            background: rgba(255, 255, 255, 0.82);
            box-shadow: 0 18px 48px rgba(91, 33, 182, 0.10);
            backdrop-filter: blur(16px);
        }

        .composer-title {
            color: var(--muted);
            font-size: 0.84rem;
            font-weight: 720;
            margin-bottom: 0.35rem;
        }

        .stButton > button {
            border-radius: 6px;
            border: 1px solid #dcc6fb;
            font-weight: 650;
            color: var(--ink);
            background: #ffffff;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, var(--brand), var(--accent));
            border-color: var(--brand);
            color: #ffffff;
            box-shadow: 0 10px 24px rgba(124, 58, 237, 0.24);
        }

        .stTextInput input, .stTextArea textarea {
            border-color: #dcc6fb;
            color: var(--ink);
        }

        [data-testid="stFileUploader"] {
            border: 1px dashed #c4a5f7;
            border-radius: 8px;
            padding: 0.4rem;
            background: rgba(250, 245, 255, 0.7);
        }

        div[data-testid="stAudioInput"] {
            border-radius: 8px;
            border: 1px solid #d8b4fe;
            background: rgba(253, 244, 255, 0.72);
            padding: 0.3rem;
        }

        .login-card {
            max-width: 520px;
            margin: 4.5rem auto 1rem;
            padding: 2rem;
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.94), rgba(245, 235, 255, 0.92));
            border: 1px solid rgba(196, 165, 247, 0.56);
            box-shadow: 0 28px 80px rgba(124, 58, 237, 0.18);
        }

        .login-badge {
            display: inline-flex;
            padding: 0.38rem 0.7rem;
            border-radius: 999px;
            color: #5b21b6;
            background: #f3e8ff;
            font-size: 0.82rem;
            font-weight: 720;
            margin-bottom: 0.85rem;
        }

        @media (max-width: 720px) {
            .top-nav {
                align-items: flex-start;
                flex-direction: column;
            }

            .nav-actions {
                width: 100%;
                justify-content: flex-start;
                flex-wrap: wrap;
            }

            .app-title {
                font-size: 1.65rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    defaults = {
        "logged_in": False,
        "user_name": "",
        "user_email": "",
        "messages": [],
        "history": [],
        "show_history": False,
        "last_answer": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def save_current_chat():
    if st.session_state.messages:
        title = st.session_state.messages[0]["content"][:55]
        st.session_state.history.insert(
            0,
            {
                "title": title or "Untitled chat",
                "messages": list(st.session_state.messages),
            },
        )


def new_chat():
    save_current_chat()
    st.session_state.messages = []
    st.session_state.last_answer = ""


def ask_api(messages, system_prompt):
    if not API_KEY:
        return "Missing OLLAMA_API_KEY. Add it in Streamlit secrets or environment variables."

    response = requests.post(
        CHAT_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "stream": False,
            "messages": [{"role": "system", "content": system_prompt.strip()}] + messages,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def extract_file_text(uploaded_file):
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()

    if name.endswith(".docx"):
        document = docx.Document(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()

    return data.decode("utf-8", errors="ignore").strip()


def summarize_document(text):
    chunks = [text[i:i + 12000] for i in range(0, len(text), 12000)]
    summaries = []

    for chunk in chunks[:5]:
        summaries.append(
            ask_api([{"role": "user", "content": chunk}], SUMMARY_PROMPT)
        )

    if len(summaries) == 1:
        return summaries[0]

    return ask_api(
        [{"role": "user", "content": "Create one final summary:\n\n" + "\n\n".join(summaries)}],
        SUMMARY_PROMPT,
    )


def detect_audio_language(text):
    try:
        language = detect(text)
    except LangDetectException:
        language = "en"

    if language == "zh-cn":
        language = "zh-CN"
    elif language == "zh-tw":
        language = "zh-TW"

    return language if language in tts_langs() else "en"


def audio_bytes(text):
    audio = gTTS(text=text, lang=detect_audio_language(text))
    buffer = BytesIO()
    audio.write_to_fp(buffer)
    buffer.seek(0)
    return buffer


def render_audio(text):
    try:
        st.audio(audio_bytes(text), format="audio/mp3")
    except Exception as error:
        st.caption(f"Audio unavailable: {error}")


def transcribe_audio(uploaded_audio):
    if uploaded_audio is None:
        return ""

    if sr is None:
        return "Audio captured, but speech recognition is not installed. Add SpeechRecognition to requirements.txt."

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(uploaded_audio) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio)
    except Exception as error:
        return f"Could not understand the audio clearly: {error}"


def login_view():
    st.markdown(
        """
        <div class="login-card">
            <div class="login-badge">Light violet research workspace</div>
            <h1 class="app-title">AI Research Agent</h1>
            <p class="app-subtitle">Sign in to continue your research chats, summarize documents, and hear answers aloud.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        name = st.text_input("Name", placeholder="Enter your name")
        email = st.text_input("Email", placeholder="you@example.com")
        submitted = st.form_submit_button("Enter Research Desk", type="primary")

    if submitted and name.strip() and email.strip():
        st.session_state.user_name = name.strip()
        st.session_state.user_email = email.strip()
        st.session_state.logged_in = True
        st.rerun()
    elif submitted:
        st.error("Please enter both your name and email.")


def render_nav():
    st.markdown(
        f"""
        <div class="top-nav">
            <div class="brand-lockup">
                <div class="brand-mark">AI</div>
                <div>
                    <div class="brand-title">{APP_NAME}</div>
                    <div class="brand-subtitle">Research chat, document insight, and voice replies</div>
                </div>
            </div>
            <div class="nav-actions">
                <span>{st.session_state.user_name}</span>
                <span>{st.session_state.user_email}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_cols = st.columns([1, 1, 1, 5])
    if nav_cols[0].button("New chat", use_container_width=True):
        new_chat()
        st.rerun()
    if nav_cols[1].button("Previous chats", use_container_width=True):
        st.session_state.show_history = not st.session_state.show_history
        st.rerun()
    if nav_cols[2].button("Logout", use_container_width=True):
        save_current_chat()
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.session_state.user_email = ""
        st.session_state.messages = []
        st.rerun()


def render_history():
    if not st.session_state.show_history:
        return

    st.markdown('<div class="history-panel">', unsafe_allow_html=True)
    st.subheader("Previous chats")
    if not st.session_state.history:
        st.caption("No previous chats yet. Start a conversation and it will appear here.")
    for index, item in enumerate(st.session_state.history):
        if st.button(item["title"], key=f"history_{index}", use_container_width=True):
            st.session_state.messages = list(item["messages"])
            st.session_state.show_history = False
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_composer():
    st.markdown('<div class="composer"><div class="composer-title">Message composer</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Attach research file",
        type=["pdf", "docx", "txt", "md", "csv"],
        label_visibility="collapsed",
    )

    input_cols = st.columns([6, 1.2, 1.2, 1.2])
    prompt = input_cols[0].text_area(
        "Message",
        placeholder="Ask your research question...",
        height=84,
        label_visibility="collapsed",
    )

    audio_prompt = None
    with input_cols[1]:
        if hasattr(st, "audio_input"):
            audio_prompt = st.audio_input("Voice", label_visibility="collapsed")
        else:
            st.caption("Voice input needs a newer Streamlit.")

    with input_cols[2]:
        summarize_clicked = st.button("Summarize", type="primary", use_container_width=True)
        listen_clicked = st.button("Listen", use_container_width=True)

    with input_cols[3]:
        send_clicked = st.button("Send", type="primary", use_container_width=True)
        clear_clicked = st.button("Clear", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if clear_clicked:
        new_chat()
        st.rerun()

    if listen_clicked:
        if st.session_state.last_answer:
            render_audio(st.session_state.last_answer)
        else:
            st.info("No bot reply to play yet.")

    if summarize_clicked:
        if not uploaded_file:
            st.warning("Attach a research document first.")
            return
        with st.spinner("Reading and summarizing document..."):
            text = extract_file_text(uploaded_file)
            if not text:
                st.error("No readable text found.")
                return
            summary = summarize_document(text)
        st.session_state.messages.append(
            {"role": "user", "content": f"Summarize uploaded document: {uploaded_file.name}"}
        )
        st.session_state.messages.append({"role": "assistant", "content": summary})
        st.session_state.last_answer = summary
        st.rerun()

    if send_clicked:
        message_text = prompt.strip()
        if audio_prompt is not None:
            transcribed = transcribe_audio(audio_prompt)
            if transcribed and not transcribed.startswith("Could not") and not transcribed.startswith("Audio captured"):
                message_text = f"{message_text}\n\n{transcribed}".strip()
            elif transcribed:
                st.warning(transcribed)

        if not message_text:
            st.warning("Type a message or record audio first.")
            return

        st.session_state.messages.append({"role": "user", "content": message_text})

        with st.spinner("Researching..."):
            try:
                answer = ask_api(st.session_state.messages, CHAT_PROMPT)
            except Exception as error:
                answer = f"Error: {error}"

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.last_answer = answer
        st.rerun()


def main_view():
    render_nav()
    render_history()
    st.markdown(
        f"""
        <div class="app-hero">
            <h1 class="app-title">Welcome, {st.session_state.user_name}</h1>
            <div class="app-subtitle">Explore papers, upload documents, ask follow-up questions, and play polished voice replies from one beautiful workspace.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message["role"] == "assistant":
                if st.button("Play reply", key=f"audio_{index}"):
                    render_audio(message["content"])
    if not st.session_state.messages:
        st.info("Start with a question, attach a research document, or record your message.")
    st.markdown("</div>", unsafe_allow_html=True)

    render_composer()


def main():
    st.set_page_config(page_title=APP_NAME, layout="wide")
    apply_design()
    init_state()

    if st.session_state.logged_in:
        main_view()
    else:
        login_view()


if __name__ == "__main__":
    main()
