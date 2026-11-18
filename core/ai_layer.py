"""Google Gemini AI client, fast model routing, OCR downscaling & timeout."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import io
import os
import re
import time
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
from core.config import AUTO, CFG

_BLOCK = ("tts", "image", "audio", "robotics", "computer-use", "customtools", "001", "3.6", "3.7", "exp", "preview")


def get_api_key() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


@st.cache_resource(show_spinner=False)
def get_client(api_key: str):
    return genai.Client(api_key=api_key)


def _speed_priority_key(name: str):
    """Prioritize low-latency Flash-Lite models first so Auto mode responds in ~1-2s."""
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    major = int(m.group(1)) if m else 0
    minor = int(m.group(2) or 0) if m else 0
    is_lite = 1 if "lite" in name else 0
    return (is_lite, major, minor)


@st.cache_data(ttl=3600, show_spinner=False)
def list_models(api_key: str):
    """Discover active free-tier Flash models, prioritizing fast Flash-Lite endpoints."""
    try:
        names = []
        for m in get_client(api_key).models.list():
            acts = getattr(m, "supported_actions", None) or []
            name = (m.name or "").replace("models/", "")
            if (
                "generateContent" in acts
                and name.startswith("gemini")
                and "flash" in name
                and not any(b in name for b in _BLOCK)
            ):
                names.append(name)
        names = sorted(set(names), key=_speed_priority_key, reverse=True)
        return names or ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
    except Exception:
        return ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]


def prepare_image(uploaded_file, max_px: int = 1024):
    """Downscale quote/bill photo so OCR uses minimal image tokens."""
    if uploaded_file is None:
        return None
    try:
        img = Image.open(uploaded_file)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            s = max_px / max(w, h)
            img = img.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
    except Exception:
        return None


def friendly_error(err: Exception) -> str:
    s = str(err)
    if isinstance(err, FuturesTimeout) or "Timeout" in s:
        return "Gemini servers timed out before completing the response. Please retry."
    if "429" in s or "RESOURCE_EXHAUSTED" in s:
        return "Free-tier rate limit reached (RPM/RPD). Wait ~20 seconds and retry."
    if "404" in s or "NOT_FOUND" in s:
        return "Selected model endpoint retired. Switch to 'Auto' or 'gemini-3.5-flash-lite'."
    if "503" in s or "UNAVAILABLE" in s:
        return "Gemini servers are temporarily busy. Retry in a few seconds."
    if "401" in s or "403" in s or "API_KEY" in s:
        return "Invalid API key. Check GEMINI_API_KEY in Streamlit secrets."
    return f"AI request could not complete: {s[:180]}"


def _gen_config(system_prompt: str, max_tokens: int) -> types.GenerateContentConfig:
    cfg = {
        "system_instruction": system_prompt,
        "temperature": 0.1,
        "max_output_tokens": max_tokens,
    }
    try:
        cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    except Exception:
        pass
    return types.GenerateContentConfig(**cfg)


def _call_with_timeout(client, model_name: str, contents, cfg, timeout_sec: int = 5):
    """Execute Gemini call with a snappy 5s timeout so busy endpoints fail fast."""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        client.models.generate_content,
        model=model_name,
        contents=contents,
        config=cfg,
    )
    try:
        return future.result(timeout=timeout_sec)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def run_llm(
    api_key: str,
    engine_choice: str,
    system_prompt: str,
    user_prompt: str,
    image_part=None,
    max_tokens: int = 500,
    stream: bool = True,
    render_inline: bool = True,
):
    """Fetch Gemini response (max 2 models; no retry on 429/auth; dynamic timeout)."""
    found = list_models(api_key)
    if engine_choice != AUTO:
        models = ([engine_choice] + [m for m in found if m != engine_choice])[:2]
    else:
        models = found[:2]

    timeout_sec = 20 if (image_part is not None or max_tokens > 500) else 8
    contents = [image_part, user_prompt] if image_part is not None else user_prompt
    cfg = _gen_config(system_prompt, max_tokens)
    client = get_client(api_key)

    last_err = None
    for idx, model_name in enumerate(models):
        status = st.empty()
        t0 = time.perf_counter()
        try:
            prefix = "Retrying with" if idx else "Contacting"
            status.info(f"⏳ {prefix} `{model_name}` ...")
            resp = _call_with_timeout(client, model_name, contents, cfg, timeout_sec=timeout_sec)
            status.empty()
            text = (resp.text or "").strip()
            if render_inline:
                st.markdown(text)

            total = time.perf_counter() - t0
            usage = getattr(resp, "usage_metadata", None)
            in_tok = getattr(usage, "prompt_token_count", 0) or 0
            out_tok = getattr(usage, "candidates_token_count", 0) or 0
            tot_tok = getattr(usage, "total_token_count", 0) or (in_tok + out_tok)
            saved = max(0, round((1 - tot_tok / CFG["baseline_tokens"]) * 100)) if tot_tok else 0
            return text, {
                "model": model_name,
                "latency": round(total, 2),
                "in_tok": in_tok,
                "out_tok": out_tok,
                "tot_tok": tot_tok,
                "saved_pct": saved,
            }
        except Exception as e:
            status.empty()
            last_err = e
            err_s = str(e)
            # Do not burn quota or waste time retrying on rate-limit or auth failures
            if any(code in err_s for code in ("429", "RESOURCE_EXHAUSTED", "401", "403", "API_KEY")):
                break

    st.error(f"❌ {friendly_error(last_err)}")
    return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def polish_letter(api_key: str, engine_choice: str, draft: str, lang: str) -> tuple[str, bool]:
    """Polishes formal DISCOM / State agency application letter. Returns (text, ok)."""
    sys_p = (
        f"You are an Indian regulatory correspondence editor. Rewrite the letter in crisp formal "
        f"{'Hindi (Devanagari)' if lang == 'Hindi' else 'English'}. "
        f"Preserve EVERY number, kW, HP, ₹ amount, state, agency and applicant name verbatim. "
        f"Output ONLY the letter text with no commentary."
    )
    found = list_models(api_key)
    models = (
        ([engine_choice] + [m for m in found if m != engine_choice])[:2]
        if engine_choice != AUTO
        else found[:2]
    )
    cfg = _gen_config(sys_p, 650)
    client = get_client(api_key)
    for m in models:
        try:
            r = _call_with_timeout(client, m, draft, cfg, timeout_sec=15)
            if r.text:
                return r.text.strip(), True
        except Exception as e:
            if any(code in str(e) for code in ("429", "RESOURCE_EXHAUSTED", "401", "403", "API_KEY")):
                break
    return draft, False
