"""Google Gemini AI client, model fallback discovery, OCR downscaling & streaming."""

import io
import os
import re
import time
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
from core.config import AUTO, CFG

_BLOCK = ("tts", "image", "audio", "robotics", "computer-use", "customtools", "001")


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


def _version_key(name: str):
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    major = int(m.group(1)) if m else 0
    minor = int(m.group(2) or 0) if m else 0
    return (major, minor, "lite" in name, "latest" in name)


@st.cache_data(ttl=3600, show_spinner=False)
def list_models(api_key: str):
    """Discover free-tier Flash models and skip retired 3.7 endpoints."""
    try:
        names = []
        for m in get_client(api_key).models.list():
            acts = getattr(m, "supported_actions", None) or []
            name = (m.name or "").replace("models/", "")
            if (
                "generateContent" in acts
                and name.startswith("gemini")
                and "flash" in name
                and "3.7" not in name
                and not any(b in name for b in _BLOCK)
            ):
                names.append(name)
        names = sorted(set(names), key=_version_key, reverse=True)
        return names or ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
    except Exception:
        return ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]


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
    if "429" in s or "RESOURCE_EXHAUSTED" in s:
        return "Free-tier rate limit reached (RPM/RPD). Wait ~30 seconds or switch model."
    if "404" in s or "NOT_FOUND" in s:
        return "Selected model endpoint retired. Switch to 'Auto' or 'gemini-3.6-flash'."
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


def run_llm(
    api_key: str,
    engine_choice: str,
    system_prompt: str,
    user_prompt: str,
    image_part=None,
    max_tokens: int = 500,
    stream: bool = True,
):
    """Stream or fetch Gemini response with automatic 4-model fallback."""
    found = list_models(api_key)
    if engine_choice != AUTO:
        models = [engine_choice] + [m for m in found if m != engine_choice][:3]
    else:
        models = found[:4]

    contents = [image_part, user_prompt] if image_part is not None else user_prompt
    cfg = _gen_config(system_prompt, max_tokens)
    client = get_client(api_key)

    last_err = None
    for idx, model_name in enumerate(models):
        status = st.empty()
        out = st.empty()
        t0 = time.perf_counter()
        ttft = None
        chunks = []
        usage = None
        try:
            prefix = "Retrying with" if idx else "Contacting"
            status.info(f"⏳ {prefix} `{model_name}` ...")
            if stream:
                for chunk in client.models.generate_content_stream(
                    model=model_name, contents=contents, config=cfg
                ):
                    if chunk.text:
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                            status.empty()
                        chunks.append(chunk.text)
                        out.markdown("".join(chunks) + " ▌")
                    if getattr(chunk, "usage_metadata", None):
                        usage = chunk.usage_metadata
                status.empty()
                text = "".join(chunks)
                out.markdown(text)
            else:
                resp = client.models.generate_content(
                    model=model_name, contents=contents, config=cfg
                )
                status.empty()
                text = resp.text or ""
                out.markdown(text)
                usage = getattr(resp, "usage_metadata", None)

            total = time.perf_counter() - t0
            in_tok = getattr(usage, "prompt_token_count", 0) or 0
            out_tok = getattr(usage, "candidates_token_count", 0) or 0
            tot_tok = getattr(usage, "total_token_count", 0) or (in_tok + out_tok)
            saved = max(0, round((1 - tot_tok / CFG["baseline_tokens"]) * 100)) if tot_tok else 0
            return text, {
                "model": model_name,
                "ttft": round(ttft or total, 2),
                "total": round(total, 2),
                "in_tok": in_tok,
                "out_tok": out_tok,
                "tot_tok": tot_tok,
                "saved_pct": saved,
            }
        except Exception as e:
            status.empty()
            out.empty()
            last_err = e

    st.error(f"❌ {friendly_error(last_err)}")
    return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def polish_letter(api_key: str, engine_choice: str, draft: str, lang: str) -> str:
    """Polishes formal DISCOM / State agency application letter."""
    sys_p = (
        f"You are an Indian regulatory correspondence editor. Rewrite the letter in crisp formal "
        f"{'Hindi (Devanagari)' if lang == 'Hindi' else 'English'}. "
        f"Preserve EVERY number, kW, HP, ₹ amount, state, agency and applicant name verbatim. "
        f"Output ONLY the letter text with no commentary."
    )
    found = list_models(api_key)
    models = (
        [engine_choice] + [m for m in found if m != engine_choice][:3]
        if engine_choice != AUTO
        else found[:4]
    )
    cfg = _gen_config(sys_p, 650)
    client = get_client(api_key)
    for m in models:
        try:
            r = client.models.generate_content(model=m, contents=draft, config=cfg)
            if r.text:
                return r.text.strip()
        except Exception:
            continue
    return draft
