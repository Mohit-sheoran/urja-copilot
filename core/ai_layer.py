"""Gemini AI helper layer for UrjaMitra (reports, vision, letter polish, and Q&A)."""

from __future__ import annotations

import json
import hashlib
import time
from typing import Any

import streamlit as st

AUTO = "Auto (Best Free/Fast)"
_DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def get_api_key() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return ""


def list_models(api_key: str) -> list[str]:
    if not api_key:
        return list(_DEFAULT_MODELS)
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        names: list[str] = []
        for m in client.models.list():
            n = getattr(m, "name", "") or ""
            short = n.split("/")[-1]
            if "gemini" in short and "embedding" not in short and "imagen" not in short:
                if short not in names:
                    names.append(short)
        return names[:8] if names else list(_DEFAULT_MODELS)
    except Exception:
        return list(_DEFAULT_MODELS)


def prepare_image(uploaded_file) -> dict[str, Any] | None:
    """Convert Streamlit UploadedFile into a standard {'mime_type': ..., 'data': bytes} dict."""
    if uploaded_file is None:
        return None
    raw = uploaded_file.getvalue()
    if not raw:
        return None
    mime = getattr(uploaded_file, "type", None) or "image/jpeg"
    return {"mime_type": mime, "data": raw}


def _order_models(api_key: str, choice: str, has_image: bool) -> list[str]:
    if choice and choice != AUTO:
        candidates = [choice] + [m for m in list_models(api_key) if m != choice]
    else:
        candidates = list_models(api_key)

    if has_image:
        non_lite = [m for m in candidates if "lite" not in m.lower()]
        lite = [m for m in candidates if "lite" in m.lower()]
        return non_lite + lite
    return candidates


def _invoke_single_model(
    api_key: str,
    model_name: str,
    sys_prompt: str,
    user_prompt: str,
    image_part: dict[str, Any] | None,
    max_tokens: int,
) -> str:
    # Try modern google-genai SDK first, then fall back to google-generativeai
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=api_key)
        contents: list[Any] = []
        if image_part:
            contents.append(
                types.Part.from_bytes(
                    data=image_part["data"],
                    mime_type=image_part["mime_type"],
                )
            )
        contents.append(user_prompt)

        cfg = types.GenerateContentConfig(
            system_instruction=sys_prompt,
            max_output_tokens=max_tokens,
            temperature=0.25,
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=cfg,
        )
        text = getattr(resp, "text", None)
        if text and text.strip():
            return text.strip()
        raise RuntimeError("Empty response from Gemini model.")
    except ImportError:
        import google.generativeai as genai_legacy  # type: ignore

        genai_legacy.configure(api_key=api_key)
        model = genai_legacy.GenerativeModel(
            model_name=model_name,
            system_instruction=sys_prompt,
        )
        parts: list[Any] = []
        if image_part:
            parts.append({"mime_type": image_part["mime_type"], "data": image_part["data"]})
        parts.append(user_prompt)
        resp = model.generate_content(
            parts,
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.25},
        )
        text = getattr(resp, "text", None)
        if text and text.strip():
            return text.strip()
        raise RuntimeError("Empty response from Gemini legacy SDK.")


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_llm_call(
    api_key_hash: str,
    model_choice: str,
    sys_prompt: str,
    user_prompt: str,
    image_bytes: bytes | None,
    image_mime: str | None,
    max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    _ = api_key_hash
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY.")

    img_part = {"mime_type": image_mime or "image/jpeg", "data": image_bytes} if image_bytes else None
    models = _order_models(api_key, model_choice, has_image=img_part is not None)

    last_err: Exception | None = None
    t0 = time.perf_counter()
    for m_name in models:
        for attempt in range(2):
            try:
                out_text = _invoke_single_model(api_key, m_name, sys_prompt, user_prompt, img_part, max_tokens)
                latency = round(time.perf_counter() - t0, 2)
                in_tok = max(1, (len(sys_prompt) + len(user_prompt)) // 4)
                out_tok = max(1, len(out_text) // 4)
                tot_tok = in_tok + out_tok
                saved_pct = max(0, round(((1800 - tot_tok) / 1800) * 100))
                metrics = {
                    "model": m_name,
                    "latency": latency,
                    "in_tok": in_tok,
                    "out_tok": out_tok,
                    "tot_tok": tot_tok,
                    "saved_pct": saved_pct,
                }
                return out_text, metrics
            except Exception as exc:
                last_err = exc
                if attempt == 0:
                    time.sleep(0.5)

    raise RuntimeError(f"All Gemini attempts failed: {last_err}")


def run_llm(
    api_key: str,
    model_choice: str,
    sys_prompt: str,
    user_prompt: str,
    image_part: dict[str, Any] | None = None,
    max_tokens: int = 450,
    stream: bool = False,
    render_inline: bool = False,
) -> tuple[str, dict[str, Any] | None]:
    _ = stream
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    key_digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    img_bytes = image_part["data"] if image_part else None
    img_mime = image_part["mime_type"] if image_part else None

    text, metrics = _cached_llm_call(
        key_digest,
        model_choice,
        sys_prompt,
        user_prompt,
        img_bytes,
        img_mime,
        max_tokens,
    )
    if render_inline and text:
        st.markdown(text)
    return text, metrics


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_polish_letter(
    api_key_hash: str,
    model_choice: str,
    draft_letter: str,
    lang: str,
) -> str:
    _ = api_key_hash
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY.")

    target_lang = "Hindi (Devanagari)" if lang == "Hindi" else "English"
    sys_p = (
        f"You are an official Indian solar subsidy application editor. Polish the wording in {target_lang} "
        "so it reads formally and clearly for a DISCOM or state nodal agency. "
        "CRITICAL RULE: Preserve EVERY number, rupee figure, kW/HP capacity, date, and scheme name verbatim. "
        "Do NOT invent or alter any figures."
    )
    usr_p = f"Polish the wording of this application letter while keeping every figure unchanged:\n\n{draft_letter}"
    polished, _ = _cached_llm_call(
        hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16],
        model_choice,
        sys_p,
        usr_p,
        None,
        None,
        900,
    )
    return polished


def polish_letter(api_key: str, model_choice: str, draft_letter: str, lang: str) -> tuple[str, bool]:
    """Polish letter wording; raises on failure so st.cache_data never caches errors."""
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing.")
    key_digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    polished = _cached_polish_letter(key_digest, model_choice, draft_letter, lang)
    return polished, True
  QUOTE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "quoted_total_inr": {
            "type": "NUMBER",
            "description": "Total final quote amount in INR (0 if not clearly visible).",
        },
        "system_size_value": {
            "type": "NUMBER",
            "description": "System capacity in kW or HP (0 if not clearly visible).",
        },
        "system_size_unit": {
            "type": "STRING",
            "description": "Unit of capacity: 'kW', 'HP', or 'UNKNOWN'.",
        },
        "panel_brand_and_spec": {
            "type": "STRING",
            "description": "Solar module brand and wattage if listed, else 'Not specified'.",
        },
        "is_dcr_mentioned": {
            "type": "BOOLEAN",
            "description": "True only if DCR / Domestic Content Requirement is explicitly written.",
        },
        "is_almm_mentioned": {
            "type": "BOOLEAN",
            "description": "True only if ALMM is explicitly written.",
        },
        "inverter_or_pump_spec": {
            "type": "STRING",
            "description": "Inverter or solar pump brand/rating if listed, else 'Not specified'.",
        },
        "earthing_and_spd_included": {
            "type": "BOOLEAN",
            "description": "True if AC/DC earthing or surge protection (SPD) is listed in BoM.",
        },
        "unreadable_or_missing_notes": {
            "type": "STRING",
            "description": "Brief note on any key item missing or blurry in the document.",
        },
    },
    "required": [
        "quoted_total_inr",
        "system_size_value",
        "system_size_unit",
        "panel_brand_and_spec",
        "is_dcr_mentioned",
        "is_almm_mentioned",
        "inverter_or_pump_spec",
        "earthing_and_spd_included",
        "unreadable_or_missing_notes",
    ],
}


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_extract_quote(
    api_key_hash: str,
    model_choice: str,
    image_bytes: bytes,
    image_mime: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _ = api_key_hash
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY.")

    models = _order_models(api_key, model_choice, has_image=True)
    sys_p = (
        "You extract structured data from Indian solar rooftop or PM-KUSUM pump quotations. "
        "Extract ONLY facts explicitly visible in the image. Never guess or invent prices or certifications."
    )
    usr_p = "Extract all solar quotation fields from this document."

    last_err: Exception | None = None
    t0 = time.perf_counter()
    for m_name in models:
        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore

            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=m_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
                    usr_p,
                ],
                config=types.GenerateContentConfig(
                    system_instruction=sys_p,
                    response_mime_type="application/json",
                    response_schema=QUOTE_SCHEMA,
                    max_output_tokens=450,
                    temperature=0.0,
                ),
            )
            raw_json = getattr(resp, "text", "") or ""
            parsed = json.loads(raw_json)
            latency = round(time.perf_counter() - t0, 2)
            metrics = {
                "model": m_name,
                "latency": latency,
                "in_tok": 280,
                "out_tok": max(1, len(raw_json) // 4),
                "tot_tok": 280 + max(1, len(raw_json) // 4),
                "saved_pct": max(0, round(((1800 - (280 + len(raw_json) // 4)) / 1800) * 100)),
            }
            return parsed, metrics
        except Exception as exc:
            last_err = exc

    raise RuntimeError(f"Structured quote extraction failed: {last_err}")


def extract_quote_fields(
    api_key: str,
    model_choice: str,
    image_part: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """LLM reads quote photo into strict JSON schema; raises on error so failures aren't cached."""
    if not api_key or not image_part:
        raise RuntimeError("API key and quote image are required.")
    key_digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    return _cached_extract_quote(
        key_digest,
        model_choice,
        image_part["data"],
        image_part["mime_type"],
    )
