import os
import html
import base64
import re
from contextlib import contextmanager
from io import BytesIO

import docx
import PyPDF2
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from gtts import gTTS
    from gtts.lang import tts_langs
    from langdetect import LangDetectException, detect
except ImportError:
    gTTS = None
    tts_langs = None
    LangDetectException = Exception
    detect = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None


APP_NAME = "AI Research Agent"
LOGIN_BACKGROUND_IMAGE = "2d35de86b73bc5c61178cfc707093dad.jpg"

CHAT_PROMPT = """
You are a professional AI research agent.
Answer clearly, accurately, and in the same language as the user.
When useful, structure the answer with concise points.
"""

def get_secret(name, default=None):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


def load_api_config():
    api_key = get_secret("OLLAMA_API_KEY")
    base_url = get_secret("OLLAMA_BASE_URL", "https://ollama.com")
    model = get_secret("OLLAMA_MODEL", "gpt-oss:20b")

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


def image_background_value(filename):
    path = os.path.join(os.getcwd(), filename)
    if not os.path.exists(path):
        return "linear-gradient(135deg, #3c225f, #9a7ac7)"

    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")

    extension = os.path.splitext(filename)[1].lower().lstrip(".") or "jpeg"
    if extension == "jpg":
        extension = "jpeg"
    return f"url('data:image/{extension};base64,{encoded}')"


@contextmanager
def no_proxy_env():
    proxy_names = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
    old_values = {name: os.environ.get(name) for name in proxy_names}
    try:
        for name in proxy_names:
            os.environ.pop(name, None)
        yield
    finally:
        for name, value in old_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def apply_design():
    login_background = image_background_value(LOGIN_BACKGROUND_IMAGE)
    st.markdown(
        """
        <style>
        :root {
            --bg: #243A66;
            --panel: rgba(255, 105, 180, 0.14);
            --panel-soft: rgba(255, 255, 255, 0.10);
            --ink: #ffe7f3;
            --muted: #f3b2cf;
            --line: rgba(255, 105, 180, 0.24);
            --brand: #FF69B4;
            --brand-dark: #800021;
            --accent: #C24366;
            --mint: #881144;
            --sun: #243A66;
        }

        .stApp {
            background:
                linear-gradient(135deg, rgba(25, 35, 82, 0.54), rgba(74, 20, 94, 0.48)),
                __LOGIN_BACKGROUND__;
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: var(--ink);
        }

        .stApp:has(.login-page) {
            background:
                linear-gradient(135deg, rgba(16, 18, 45, 0.30), rgba(42, 20, 72, 0.24)),
                __LOGIN_BACKGROUND__;
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }

        .stApp:has(.login-page) .block-container {
            max-width: 430px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 1.6rem 1.2rem;
        }

        .stApp, .stMarkdown, .stText, label, p, h1, h2, h3, h4, h5, h6 {
            color: var(--ink);
        }

        [data-testid="stSidebar"] {
            display: none;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 1060px;
            padding-top: 0.85rem;
            padding-bottom: 1.5rem;
        }

        .app-hero {
            padding: 0.2rem 0 0.7rem;
            border: 0;
            background: transparent;
            box-shadow: none;
            margin-bottom: 0.2rem;
        }

        .hero-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }

        .hero-user {
            color: var(--muted);
            font-size: 0.86rem;
            text-align: right;
        }

        .app-title {
            font-size: 1.72rem;
            font-weight: 860;
            letter-spacing: 0;
            margin: 0;
            color: #061E42;
        }

        .app-subtitle {
            color: #f8d7ec;
            margin-top: 0.25rem;
            font-size: 0.92rem;
            line-height: 1.5;
        }

        .chat-shell {
            padding: 0.15rem 0 0.45rem;
        }

        .empty-note {
            color: #fff1f9;
            font-size: 0.94rem;
            margin: 0.25rem 0 0.65rem;
            padding: 0.85rem 1rem;
            border-radius: 8px;
            background: rgba(20, 24, 48, 0.38);
            border: 1px solid rgba(255, 255, 255, 0.18);
            backdrop-filter: blur(12px);
        }

        .chat-bubble {
            border-radius: 8px;
            padding: 0.85rem 1rem;
            margin: 0.55rem 0;
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 14px 32px rgba(20, 4, 28, 0.18);
            line-height: 1.55;
        }

        .chat-role {
            font-size: 0.72rem;
            font-weight: 780;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
            opacity: 0.78;
        }

        .user-bubble {
            background: linear-gradient(135deg, rgba(255, 105, 180, 0.20), rgba(194, 67, 102, 0.20), rgba(36, 58, 102, 0.68));
            color: #fff4fa;
        }

        .assistant-bubble {
            background: linear-gradient(135deg, rgba(36, 58, 102, 0.88), rgba(128, 0, 33, 0.72));
            color: #ffe7f3;
        }

        .stChatMessage {
            border-radius: 8px;
            border: 1px solid var(--line);
            box-shadow: 0 16px 34px rgba(10, 2, 22, 0.26);
            background: rgba(189, 216, 233, 0.12);
            color: var(--ink);
            backdrop-filter: blur(14px);
        }

        .composer {
            padding: 0.72rem 0.78rem;
            margin-top: 0.2rem;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            background:
                linear-gradient(135deg, rgba(26, 33, 68, 0.82), rgba(80, 34, 116, 0.78), rgba(119, 46, 110, 0.78));
            box-shadow: 0 22px 58px rgba(47, 24, 80, 0.34);
            backdrop-filter: blur(18px);
        }

        .stButton > button, .stFormSubmitButton > button {
            min-height: 2.7rem;
            width: 100%;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.24);
            font-weight: 760;
            color: #ffffff;
            background: linear-gradient(135deg, #4C1D95, #7E22CE);
            box-shadow: 0 12px 28px rgba(76, 29, 149, 0.24);
            white-space: nowrap;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #7C3AED, #EC4899);
            border-color: rgba(233, 213, 255, 0.72);
            color: #ffffff;
            box-shadow: 0 14px 32px rgba(124, 58, 237, 0.26);
        }

        .stFormSubmitButton > button[kind="primary"] {
            background: linear-gradient(135deg, #0B3A75, #126C8F);
            border-color: rgba(123, 189, 232, 0.72);
            color: #ffffff;
            box-shadow: 0 14px 34px rgba(11, 58, 117, 0.24);
        }

        .stButton > button:hover, .stFormSubmitButton > button:hover {
            border-color: rgba(255, 255, 255, 0.42);
            transform: translateY(-1px);
        }

        .stTextInput input, .stTextArea textarea {
            min-height: 2.75rem;
            border: 1px solid rgba(255, 255, 255, 0.24);
            border-radius: 6px;
            color: #ffe7f3 !important;
            background: rgba(36, 58, 102, 0.92) !important;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
        }

        .stTextInput input::placeholder, .stTextArea textarea::placeholder {
            color: #f3b2cf;
        }

        div[data-baseweb="input"] {
            background: rgba(36, 58, 102, 0.92) !important;
            border-radius: 6px;
        }

        div[data-baseweb="input"] input {
            color: #ffe7f3 !important;
            -webkit-text-fill-color: #ffe7f3 !important;
        }

        [data-testid="stForm"] {
            border: 0;
            padding: 0;
            background: transparent;
        }

        [data-testid="stForm"] > div {
            border: 0;
            padding: 0;
            background: transparent;
        }

        [data-testid="stFileUploader"] {
            position: relative;
            min-height: 2.7rem;
            height: 2.7rem;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.24);
            border-radius: 8px;
            padding: 0;
            background: linear-gradient(135deg, #4C1D95, #8B5CF6);
            box-shadow: 0 10px 22px rgba(76, 29, 149, 0.24);
        }

        [data-testid="stFileUploader"]::before {
            content: "\\1F4CE";
            position: absolute;
            inset: 0;
            display: grid;
            place-items: center;
            color: #ffffff;
            font-size: 1.28rem;
            pointer-events: none;
            z-index: 2;
        }

        [data-testid="stFileUploader"] * {
            color: #ffffff;
            font-weight: 760;
        }

        [data-testid="stFileUploader"] section {
            opacity: 0;
            min-height: 2.7rem;
            height: 2.7rem;
            padding: 0;
            border: 0;
            background: transparent;
        }

        [data-testid="stFileUploader"] section > div {
            padding: 0.15rem 0.2rem;
        }

        [data-testid="stFileUploader"] small,
        [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] {
            display: none;
        }

        [data-testid="stFileUploader"] button {
            min-height: 2.2rem;
            width: 100%;
            border-radius: 6px;
            border: 0;
            color: #ffffff;
            font-size: 0;
            background: rgba(255, 255, 255, 0.16);
        }

        [data-testid="stFileUploader"] button::before {
            content: "";
            font-size: 1.25rem;
            line-height: 1;
        }

        div[data-testid="stAudioInput"] {
            position: relative;
            min-height: 2.7rem;
            height: 2.7rem;
            overflow: hidden;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.24);
            background: linear-gradient(135deg, #6D28D9, #A855F7);
            padding: 0.12rem 0.24rem;
            box-shadow: 0 10px 22px rgba(109, 40, 217, 0.26);
        }

        div[data-testid="stAudioInput"]::before {
            content: "\\1F399";
            position: absolute;
            inset: 0;
            display: grid;
            place-items: center;
            color: #ffffff;
            font-size: 1.2rem;
            pointer-events: none;
            z-index: 2;
            animation: micPulse 1.05s ease-in-out infinite;
        }

        div[data-testid="stAudioInput"]::after {
            content: "";
            position: absolute;
            right: 0.42rem;
            top: 50%;
            width: 0.18rem;
            height: 0.85rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.90);
            box-shadow:
                -0.38rem 0 0 rgba(255, 255, 255, 0.78),
                -0.76rem 0 0 rgba(255, 255, 255, 0.58);
            transform: translateY(-50%);
            animation: recordingBars 0.72s ease-in-out infinite;
            pointer-events: none;
            z-index: 4;
        }

        div[data-testid="stAudioInput"] * {
            color: #ffffff;
            font-weight: 760;
        }

        div[data-testid="stAudioInput"] button {
            min-height: 2.2rem;
            width: 100%;
            border-radius: 6px;
            border: 0;
            color: #ffffff !important;
            font-size: 0;
            background: rgba(88, 28, 135, 0.84) !important;
            position: relative;
            z-index: 3;
        }

        div[data-testid="stAudioInput"] button:hover {
            background: rgba(76, 29, 149, 0.96) !important;
        }

        div[data-testid="stAudioInput"] svg {
            color: #ffffff !important;
            fill: #ffffff !important;
            stroke: #ffffff !important;
        }

        div[data-testid="stAudioInput"] button::before {
            content: "";
            font-size: 1.15rem;
            line-height: 1;
        }

        .voice-ready {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin: 0.45rem 0 0;
            padding: 0.34rem 0.58rem;
            border-radius: 999px;
            color: #faf5ff;
            background: rgba(88, 28, 135, 0.76);
            border: 1px solid rgba(216, 180, 254, 0.48);
            box-shadow: 0 10px 22px rgba(88, 28, 135, 0.18);
            font-size: 0.8rem;
            font-weight: 720;
            width: fit-content;
            max-width: 100%;
        }

        .file-ready {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin: 0.45rem 0 0;
            padding: 0.34rem 0.58rem;
            border-radius: 999px;
            color: #eff6ff;
            background: rgba(30, 64, 175, 0.72);
            border: 1px solid rgba(191, 219, 254, 0.46);
            box-shadow: 0 10px 22px rgba(30, 64, 175, 0.18);
            font-size: 0.8rem;
            font-weight: 720;
            width: fit-content;
            max-width: 100%;
        }

        .file-ready-name {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: min(34rem, 72vw);
        }

        .voice-ready-dot {
            width: 0.48rem;
            height: 0.48rem;
            border-radius: 999px;
            background: #E9D5FF;
            box-shadow: 0 0 0 0 rgba(233, 213, 255, 0.76);
            animation: readyPulse 1.15s ease-out infinite;
        }

        .chat-bubble audio {
            width: 100%;
            max-width: 20rem;
            margin-top: 0.35rem;
            filter: saturate(1.08);
        }

        @keyframes micPulse {
            0%, 100% {
                transform: scale(1);
                opacity: 1;
            }
            50% {
                transform: scale(1.16);
                opacity: 0.76;
            }
        }

        @keyframes recordingBars {
            0%, 100% {
                height: 0.55rem;
                box-shadow:
                    -0.38rem 0 0 rgba(255, 255, 255, 0.60),
                    -0.76rem 0 0 rgba(255, 255, 255, 0.36);
            }
            50% {
                height: 1.25rem;
                box-shadow:
                    -0.38rem 0 0 rgba(255, 255, 255, 0.92),
                    -0.76rem 0 0 rgba(255, 255, 255, 0.72);
            }
        }

        @keyframes readyPulse {
            0% {
                box-shadow: 0 0 0 0 rgba(233, 213, 255, 0.76);
            }
            100% {
                box-shadow: 0 0 0 0.55rem rgba(233, 213, 255, 0);
            }
        }

        .login-card {
            margin: 0 0 1.35rem;
        }

        .stApp:has(.login-page) [data-testid="stForm"] {
            padding: 2rem 1.9rem 1.6rem;
            border-radius: 8px;
            background: rgba(25, 31, 42, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.58);
            box-shadow: 0 26px 76px rgba(16, 10, 34, 0.30);
            backdrop-filter: blur(13px);
        }

        .stApp:has(.login-page) [data-testid="stForm"] > div {
            border: 0;
            padding: 0;
            background: transparent;
        }

        .login-title {
            margin: 0;
            font-size: 2rem;
            font-weight: 820;
            color: #ffffff;
        }

        .login-subtitle {
            margin: 0.25rem 0 1.45rem;
            color: rgba(255, 255, 255, 0.86);
            font-size: 0.94rem;
        }

        .stApp:has(.login-page) .stTextInput input {
            min-height: 3.15rem;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.72);
            background-color: rgba(14, 24, 54, 0.62) !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            padding-left: 1rem;
            caret-color: #ffffff;
            box-shadow: inset 0 0 0 999px rgba(14, 24, 54, 0.62);
        }

        .stApp:has(.login-page) .stTextInput input::placeholder {
            color: rgba(255, 255, 255, 0.78);
        }

        .stApp:has(.login-page) div[data-baseweb="input"] {
            border-radius: 12px;
            background: rgba(14, 24, 54, 0.62) !important;
        }

        .stApp:has(.login-page) input:-webkit-autofill,
        .stApp:has(.login-page) input:-webkit-autofill:hover,
        .stApp:has(.login-page) input:-webkit-autofill:focus {
            -webkit-text-fill-color: #ffffff !important;
            transition: background-color 9999s ease-in-out 0s;
            box-shadow: inset 0 0 0 999px rgba(14, 24, 54, 0.92) !important;
        }

        .stApp:has(.login-page) .stCheckbox {
            margin: 0.2rem 0 1rem;
        }

        .stApp:has(.login-page) .stCheckbox label,
        .stApp:has(.login-page) .stCheckbox p {
            color: rgba(255, 255, 255, 0.88);
            font-size: 0.82rem;
        }

        .stApp:has(.login-page) .stFormSubmitButton > button[kind="primary"] {
            min-height: 3.25rem;
            border-radius: 10px;
            border: 0;
            background: linear-gradient(90deg, #7C3AED, #EC4899);
            color: #ffffff;
            font-size: 1.08rem;
            box-shadow: 0 16px 34px rgba(124, 58, 237, 0.32);
        }

        @media (max-width: 720px) {
            .hero-top {
                align-items: flex-start;
                flex-direction: column;
            }

            .hero-user {
                text-align: left;
            }

            .app-title {
                font-size: 1.65rem;
            }
        }
        </style>
        """.replace("__LOGIN_BACKGROUND__", login_background),
        unsafe_allow_html=True,
    )


def init_state():
    defaults = {
        "logged_in": False,
        "user_name": "",
        "user_email": "",
        "messages": [],
        "attached_file_name": "",
        "attached_file_text": "",
        "voice_text": "",
        "voice_audio_hash": "",
        "voice_audio_bytes": None,
        "media_reset_token": 0,
        "message_reset_token": 0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def new_chat():
    st.session_state.messages = []
    st.session_state.attached_file_name = ""
    st.session_state.attached_file_text = ""
    st.session_state.voice_text = ""
    st.session_state.voice_audio_hash = ""
    st.session_state.voice_audio_bytes = None
    st.session_state.media_reset_token += 1
    st.session_state.message_reset_token += 1


def enable_enter_to_send():
    components.html(
        """
        <script>
        const doc = window.parent.document;
        if (window.parent.__researchEnterToSend) {
            doc.removeEventListener("keydown", window.parent.__researchEnterToSend, true);
        }

        window.parent.__researchEnterToSend = (event) => {
            if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) {
                return;
            }

            const active = doc.activeElement;
            const isTypingArea = active && ["INPUT", "TEXTAREA"].includes(active.tagName);
            const hasReadyItem = Boolean(doc.querySelector(".voice-ready, .file-ready"));
            if (!isTypingArea && !hasReadyItem) {
                return;
            }

            const formSubmitButtons = Array.from(
                doc.querySelectorAll('[data-testid="stFormSubmitButton"] button')
            ).filter((button) => button.offsetParent !== null);
            const sendButton = formSubmitButtons[formSubmitButtons.length - 1];

            if (sendButton) {
                event.preventDefault();
                event.stopPropagation();
                sendButton.click();
            }
        };

        doc.addEventListener("keydown", window.parent.__researchEnterToSend, true);
        </script>
        """,
        height=0,
    )


def ask_api(messages, system_prompt):
    if not API_KEY:
        return "Missing OLLAMA_API_KEY. Add it in Streamlit secrets or environment variables."

    session = requests.Session()
    session.trust_env = False

    try:
        response = session.post(
            CHAT_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "stream": False,
                "messages": [{"role": "system", "content": system_prompt.strip()}] + messages,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 500,
                },
            },
            timeout=(10, 75),
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.ProxyError:
        return "I could not reach the AI service because a broken proxy is configured on this computer. The app now bypasses system proxy settings for chat requests; restart the Streamlit app and try again."
    except requests.exceptions.ConnectTimeout:
        return "The AI service took too long to connect. Please check your internet connection and try again."
    except requests.exceptions.ConnectionError as error:
        return f"I could not connect to the AI service. Check your internet connection or Ollama base URL. Details: {error}"
    except requests.exceptions.HTTPError as error:
        return f"The AI service returned an error: {error}"


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


def detect_voice_language(text):
    if detect is None or tts_langs is None:
        return "en"

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


@st.cache_data(show_spinner=False)
def text_to_speech_bytes(text):
    if gTTS is None:
        raise RuntimeError("Text-to-speech is not installed. Add gTTS and langdetect to requirements.txt.")

    audio_buffer = BytesIO()
    with no_proxy_env():
        gTTS(text=text, lang=detect_voice_language(text)).write_to_fp(audio_buffer)
    return audio_buffer.getvalue()


def render_speech_button(text, key):
    button_col, audio_col = st.columns([0.95, 5.8])
    clicked = button_col.button("Hear", key=f"hear_{key}", use_container_width=True)

    if clicked:
        with audio_col:
            try:
                with st.spinner("Preparing voice..."):
                    audio_bytes = text_to_speech_bytes(text)
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            except Exception as error:
                st.error(f"Could not play the bot response as audio: {error}")


def transcribe_audio(uploaded_audio):
    if uploaded_audio is None:
        return ""

    if sr is None:
        return "Audio captured, but speech recognition is not installed. Add SpeechRecognition to requirements.txt."

    recognizer = sr.Recognizer()
    try:
        audio_data = BytesIO(uploaded_audio.getvalue())
        with sr.AudioFile(audio_data) as source:
            audio = recognizer.record(source)
        with no_proxy_env():
            return recognizer.recognize_google(audio)
    except Exception as error:
        return f"Could not understand the audio clearly: {error}"


def is_valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def login_view():
    st.markdown('<div class="login-page"></div>', unsafe_allow_html=True)

    with st.form("login_form"):
        st.markdown(
            """
            <div class="login-card">
                <h1 class="login-title">Login</h1>
                <p class="login-subtitle">Welcome back please login to your account</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        username = st.text_input("User Name", placeholder="User Name", label_visibility="collapsed")
        email = st.text_input("Email", placeholder="Email", label_visibility="collapsed")
        st.checkbox("Remember me", value=True)
        submitted = st.form_submit_button("Login", type="primary")

    if submitted and username.strip() and is_valid_email(email):
        st.session_state.user_name = username.strip()
        st.session_state.user_email = email.strip()
        st.session_state.logged_in = True
        st.rerun()
    elif submitted:
        st.error("Please enter your username and a valid email address.")


def render_composer():
    st.markdown('<div class="composer">', unsafe_allow_html=True)

    uploaded_file = None
    audio_prompt = None
    media_reset_token = st.session_state.media_reset_token
    message_reset_token = st.session_state.message_reset_token

    composer_cols = st.columns([0.72, 0.72, 7.35, 0.55])
    with composer_cols[0]:
        uploaded_file = st.file_uploader(
            "Upload",
            type=["pdf", "docx", "txt", "md", "csv"],
            label_visibility="collapsed",
            key=f"file_uploader_{media_reset_token}",
        )

    with composer_cols[1]:
        if hasattr(st, "audio_input"):
            audio_prompt = st.audio_input(
                "Audio",
                label_visibility="collapsed",
                key=f"audio_input_{media_reset_token}",
            )
        else:
            st.caption("Audio needs newer Streamlit.")

    with composer_cols[2]:
        with st.form(f"message_form_{message_reset_token}", clear_on_submit=True):
            form_cols = st.columns([6.35, 1.0])
            with form_cols[0]:
                prompt = st.text_input(
                    "Message",
                    placeholder="Ask your research question...",
                    label_visibility="collapsed",
                    key=f"message_prompt_{message_reset_token}",
                )
            with form_cols[1]:
                send_clicked = st.form_submit_button("\U0001F680", type="primary", use_container_width=True)

    refresh_clicked = composer_cols[3].button("\u21bb", use_container_width=True)
    send_requested = send_clicked

    if audio_prompt is not None:
        voice_audio_bytes = audio_prompt.getvalue()
        audio_hash = str(hash(voice_audio_bytes))
        if audio_hash != st.session_state.voice_audio_hash:
            st.session_state.voice_audio_hash = audio_hash
            st.session_state.voice_audio_bytes = voice_audio_bytes
            transcribed = transcribe_audio(audio_prompt)
            if transcribed and not transcribed.startswith("Could not") and not transcribed.startswith("Audio captured"):
                st.session_state.voice_text = transcribed
            elif transcribed:
                st.session_state.voice_text = ""
                st.warning(transcribed)

    if uploaded_file and uploaded_file.name != st.session_state.attached_file_name:
        with st.spinner("Reading uploaded document..."):
            text = extract_file_text(uploaded_file)
            if not text:
                st.error("No readable text found.")
                return
            st.session_state.attached_file_name = uploaded_file.name
            st.session_state.attached_file_text = text[:12000]
            st.toast(f"Attached {uploaded_file.name}")

    if st.session_state.voice_audio_bytes:
        st.markdown(
            """
            <div class="voice-ready">
                <span class="voice-ready-dot"></span>
                <span>Voice ready to send</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.attached_file_name:
        st.markdown(
            f"""
            <div class="file-ready">
                <span>Attached</span>
                <span class="file-ready-name">{html.escape(st.session_state.attached_file_name)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    enable_enter_to_send()

    st.markdown("</div>", unsafe_allow_html=True)

    if refresh_clicked:
        new_chat()
        st.rerun()

    if send_requested:
        message_key = f"message_prompt_{message_reset_token}"
        message_text = st.session_state.get(message_key, prompt).strip()
        has_voice = bool(st.session_state.voice_audio_bytes)
        has_file = bool(st.session_state.attached_file_text)
        if st.session_state.voice_text:
            message_text = f"{message_text}\n\n{st.session_state.voice_text}".strip()

        if has_voice and not message_text:
            message_text = "Voice message"
        elif has_file and not message_text:
            message_text = "Please analyze the attached file."
        elif not message_text:
            st.warning("Type a message or record audio clearly first.")
            return

        api_message = message_text
        if st.session_state.attached_file_text:
            api_message = (
                f"The user uploaded this document: {st.session_state.attached_file_name}\n\n"
                f"Document text:\n{st.session_state.attached_file_text}\n\n"
                f"User question:\n{message_text}"
            )

        display_text = st.session_state.get(message_key, prompt).strip()
        if has_voice:
            display_text = f"{display_text}\n\nVoice message".strip()

        previous_api_messages = [
            {"role": message["role"], "content": message.get("api_content", message["content"])}
            for message in st.session_state.messages[-8:]
        ]

        if display_text or has_voice:
            user_message = {
                "role": "user",
                "content": display_text or "Voice message",
                "api_content": message_text,
            }
            if has_voice:
                user_message["audio"] = st.session_state.voice_audio_bytes
            st.session_state.messages.append(user_message)

        answer = ask_api(previous_api_messages + [{"role": "user", "content": api_message}], CHAT_PROMPT)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.attached_file_name = ""
        st.session_state.attached_file_text = ""
        st.session_state.voice_text = ""
        st.session_state.voice_audio_hash = ""
        st.session_state.voice_audio_bytes = None
        st.session_state.media_reset_token += 1
        st.session_state.message_reset_token += 1
        st.rerun()


def main_view():
    logout_cols = st.columns([5.0, 1.0])
    if logout_cols[1].button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.session_state.user_email = ""
        st.session_state.messages = []
        st.session_state.attached_file_name = ""
        st.session_state.attached_file_text = ""
        st.session_state.voice_audio_bytes = None
        st.rerun()

    st.markdown(
        f"""
        <div class="app-hero">
            <div class="hero-top">
                <div>
                    <h1 class="app-title">AI Research Agent</h1>
                    <div class="app-subtitle">Welcome, {html.escape(st.session_state.user_name)}. How can I help with your research today?</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    for index, message in enumerate(st.session_state.messages):
        if message["role"] == "user" and (
            message["content"].startswith("Attached")
            or "Attached file:" in message["content"]
            or message["content"] == "File sent"
        ):
            continue

        role_label = "You" if message["role"] == "user" else "AI Research Agent"
        bubble_class = "user-bubble" if message["role"] == "user" else "assistant-bubble"
        content = html.escape(message["content"]).replace("\n", "<br>")
        st.markdown(
            f"""
            <div class="chat-bubble {bubble_class}">
                <div class="chat-role">{role_label}</div>
                <div>{content}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if message.get("audio"):
            st.audio(message["audio"], format="audio/wav")
        if message["role"] == "assistant":
            render_speech_button(message["content"], index)
    if not st.session_state.messages:
        st.markdown(
            f'<div class="empty-note">Hi {html.escape(st.session_state.user_name)}, start with a question, upload a file, or record a voice note.</div>',
            unsafe_allow_html=True,
        )
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
