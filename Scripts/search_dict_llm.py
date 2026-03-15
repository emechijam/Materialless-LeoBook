# search_dict_llm.py: LLM prompt builder, HTTP call, and metadata query functions.
# Part of LeoBook Scripts — Search Dictionary
# Imported by: build_search_dict.py only.

import json
import re
import time
import requests
import os


def _build_prompt(items, item_type="team"):
    """Builds the LLM prompt for team or league metadata enrichment."""
    items_list = "\n".join([f"- {name}" for name in items])
    if item_type == "team":
        return f"""You are a football/soccer database expert.
Here is a list of team names extracted from match schedules:
{items_list}
For EACH team, return accurate, canonical metadata in this exact JSON structure.
Use the most commonly accepted official name today.
Include alternative / historical / sponsor names when relevant.
Do NOT invent information — if uncertain, use "unknown".
Output ONLY valid JSON array of objects with these keys:
[
  {{
    "input_name": "exact name from list",
    "official_name": "most official / current name",
    "other_names": ["array", "of", "known", "aliases", "nicknames"],
    "abbreviations": ["short codes", "common abbr"],
    "country": "ISO 3166-1 alpha-2 or full country name",
    "city": "main city/base (if known)",
    "stadium": "home stadium name or null",
    "league": "primary current league (short name)",
    "founded": year or null,
    "wikipedia_url": "best Wikipedia page or null"
  }}
]
Return ONLY the JSON array - no explanations, no markdown.
"""
    else:  # league
        return f"""You are a football/soccer database expert.
Here is a list of league/competition identifiers:
{items_list}
For EACH one, return accurate, canonical metadata in this exact JSON structure.
Use the current official name (including title sponsor if it's the primary branding).
Include alternative / previous / short names.
Output ONLY valid JSON array of objects with these keys:
[
  {{
    "input_name": "exact name from list",
    "official_name": "current official name",
    "other_names": ["previous names", "short names", "sponsor variants"],
    "abbreviations": ["common short codes"],
    "level": "top-tier / second / etc or null",
    "season_format": "Apertura/Clausura, single table, etc or null",
    "wikipedia_url": "best Wikipedia page or null"
  }}
]
Return ONLY the JSON array - no explanations, no markdown.
"""


def extract_json_with_salvage(text: str) -> list:
    """
    Attempts to extract JSON from text even if malformed or truncated.
    Returns a list of salvaged objects.
    """
    if not text:
        return []

    # 1. Try standard regex for JSON block
    match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    # 2. Salvage individual objects if the array is broken
    objects = []
    potential_objects = re.findall(r'\{[^{}]*\}', text)
    for obj_str in potential_objects:
        try:
            obj = json.loads(obj_str)
            if isinstance(obj, dict) and "input_name" in obj:
                objects.append(obj)
        except Exception:
            continue

    # 3. If still empty, try to fix common truncation issues
    if not objects and "[" in text:
        try:
            salvaged = text.strip()
            if not salvaged.endswith("]"):
                if not salvaged.endswith("}"):
                    salvaged += "}"
                salvaged += "]"
            return json.loads(salvaged)
        except Exception:
            pass

    return objects


def _call_llm(provider: dict, prompt: str) -> list:
    """Calls a single LLM provider and returns parsed results.

    Raises RuntimeError with the response body embedded on non-2xx status
    so upstream handlers can detect daily-limit signals.
    """
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4096
    }
    resp = requests.post(provider["api_url"], headers=headers, json=payload, timeout=60)
    if not resp.ok:
        raise RuntimeError(
            f"{resp.status_code} {resp.reason} | body: {resp.text[:500]}"
        )
    content = resp.json()["choices"][0]["message"]["content"].strip()

    data = extract_json_with_salvage(content)
    if not data:
        print(f"  [Warning] {provider['name']} response yielded no valid JSON: {content[:200]}...")
        return []

    return [item for item in data if isinstance(item, dict) and "input_name" in item]


def query_llm_for_metadata(items, item_type="team", retries=2):
    """
    Queries LLM providers with ASCENDING model chain (cheapest first).
    For Gemini: iterates model chain x key rotation.
    On 429: inspects error body for daily-limit signal; if daily, marks model
    exhausted and downgrades. If per-minute, applies COOLDOWN and tries next key.
    """
    if not items:
        return []

    from Core.Intelligence.llm_health_manager import health_manager
    ordered = health_manager.get_ordered_providers()
    model_chain = health_manager.get_model_chain("search_dict")

    prompt = _build_prompt(items, item_type)

    for provider_name in ordered:
        if not health_manager.is_provider_active(provider_name):
            print(f"  [Skip] {provider_name} - inactive per health check.")
            continue

        if provider_name == "Gemini":
            consecutive_429s = 0
            for model_name in model_chain:
                if health_manager.is_model_daily_exhausted(model_name):
                    print(f"  [Skip] {model_name} - daily quota exhausted.")
                    continue
                while True:
                    api_key = health_manager.get_next_gemini_key(model=model_name)
                    if not api_key:
                        wait_secs = health_manager.get_cooldown_remaining(model_name)
                        if wait_secs > 0:
                            print(f"  [LLM] All keys cooling down for {model_name}. Waiting {wait_secs:.0f}s...")
                            time.sleep(wait_secs + 1)
                            api_key = health_manager.get_next_gemini_key(model=model_name)
                        if not api_key:
                            print(f"  [LLM] All keys exhausted for {model_name}, downgrading model...")
                            break
                    provider = {
                        "name": "Gemini",
                        "api_key": api_key,
                        "api_url": health_manager.GEMINI_API_URL,
                        "model": model_name,
                    }
                    for attempt in range(1, retries + 1):
                        try:
                            key_suffix = api_key[-4:]
                            print(f"  [LLM] Gemini {model_name} (key ...{key_suffix}) attempt {attempt}/{retries}...")
                            results = _call_llm(provider, prompt)
                            if results:
                                print(f"  [LLM] Gemini {model_name} returned {len(results)} items.")
                                consecutive_429s = 0
                                return results
                        except Exception as e:
                            err_str = str(e)
                            if "429" in err_str:
                                health_manager.on_gemini_429(api_key, model=model_name, err_str=err_str)
                                consecutive_429s += 1
                                if health_manager.is_model_daily_exhausted(model_name):
                                    break
                                backoff = min(2 ** consecutive_429s, 30)
                                print(f"  [LLM] Key ...{key_suffix} rate-limited on {model_name}, backoff {backoff}s...")
                                time.sleep(backoff)
                                break
                            elif "400" in err_str and "INVALID_ARGUMENT" in err_str:
                                health_manager.on_gemini_fatal_error(api_key, "400 Invalid Argument")
                                break
                            elif "401" in err_str or "UNAUTHORIZED" in err_str:
                                health_manager.on_gemini_fatal_error(api_key, "401 Unauthorized")
                                break
                            elif "403" in err_str:
                                health_manager.on_gemini_fatal_error(api_key, "403 Forbidden")
                                break
                            print(f"  [Warning] Gemini {model_name} attempt {attempt}/{retries} failed: {e}")
                            time.sleep(3 * attempt)
                    else:
                        continue
                    continue

            print(f"  [Fallback] Gemini exhausted all models. Trying next provider...")

        elif provider_name == "Grok":
            grok_key = os.getenv("GROK_API_KEY", "")
            if not grok_key:
                print(f"  [Skip] Grok - no API key configured.")
                continue
            provider = {
                "name": "Grok",
                "api_key": grok_key,
                "api_url": health_manager.GROK_API_URL,
                "model": health_manager.GROK_MODEL,
            }
            for attempt in range(1, retries + 1):
                try:
                    print(f"  [LLM] Grok attempt {attempt}/{retries}...")
                    results = _call_llm(provider, prompt)
                    if results:
                        print(f"  [LLM] Grok returned {len(results)} items.")
                        return results
                except Exception as e:
                    print(f"  [Warning] Grok attempt {attempt}/{retries} failed: {e}")
                    time.sleep(3 * attempt)
            print(f"  [Fallback] Grok exhausted. Trying next provider...")

    print(f"  [Error] All LLM providers failed for {len(items)} {item_type}(s).")
    return []


import asyncio as _asyncio


async def async_query_llm_for_metadata(items, item_type="team", retries=2):
    """Async wrapper that ensures health manager is initialized before sync LLM call."""
    from Core.Intelligence.llm_health_manager import health_manager
    await health_manager.ensure_initialized()
    return await _asyncio.to_thread(query_llm_for_metadata, items, item_type, retries)


# Backward-compatible alias
query_grok_for_metadata_with_retry = async_query_llm_for_metadata


__all__ = [
    "_build_prompt",
    "extract_json_with_salvage",
    "_call_llm",
    "query_llm_for_metadata",
    "async_query_llm_for_metadata",
    "query_grok_for_metadata_with_retry",
]
