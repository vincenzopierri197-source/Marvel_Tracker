#!/usr/bin/env python3
"""Aggiorna in modo prudente il catalogo Marvel usando Gemini + Google Search grounding.

Le sezioni curate (ordini Marvel e uscita) non vengono mai riscritte dall'AI.
Le notizie sono mostrate separatamente e includono link restituiti dal grounding.
I nuovi titoli vengono proposti in una sezione distinta solo se hanno fonte URL.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "marvel.json"
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
TIMEOUT = 90
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def slug(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def valid_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", text, flags=re.I)
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("Gemini non ha restituito un oggetto JSON.")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("La risposta Gemini non è un oggetto JSON.")
    return value


def call_gemini(api_key: str, data: dict) -> tuple[dict, list[dict], list[str]]:
    existing_titles = [
        item.get("title", "")
        for order in data.get("orders", {}).values()
        for section in order.get("sections", [])
        for item in section.get("items", [])
        if item.get("title")
    ]
    prompt = f"""
Sei un ricercatore editoriale per un tracker Marvel in lingua italiana.
Usa Google Search per trovare aggiornamenti verificabili pubblicati o confermati
di recente su film, serie, date d'uscita, trailer, casting e annunci ufficiali
Marvel Studios / Marvel Television. Dai priorità a Marvel.com, Disney+, comunicati
ufficiali e fonti giornalistiche affidabili. Distingui le date confermate dalle
indiscrezioni; escludi rumor non confermati. La data corrente è {datetime.now(timezone.utc).date().isoformat()}.
Titoli già presenti nel catalogo (non proporli come nuovi): {json.dumps(existing_titles, ensure_ascii=False)}.
Rispondi SOLO con JSON valido, senza Markdown, con questa struttura:
{{
 "researchUpdates":[
  {{"title":"titolo breve in italiano","summary":"riassunto fattuale breve in italiano, specifica se ufficiale o rumor","date":"YYYY-MM-DD oppure stringa vuota","sources":[{{"title":"titolo fonte","url":"URL esatto"}}]}}
 ],
 "sourceUpdates":[
  {{"title":"titolo ufficiale film/serie Marvel nuovo o appena confermato","type":"film oppure serie","year":2027,"source":"URL esatto della fonte"}}
 ]
}}
Massimo 8 notizie e 8 titoli nuovi. Ogni notizia deve avere almeno una fonte URL.
Non inventare URL o date. Se non trovi novità affidabili, usa liste vuote.
"""

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    response = requests.post(
        API_URL,
        params={"key": api_key},
        json=payload,
        timeout=TIMEOUT,
    )
    if not response.ok:
        detail = response.text[:1200]
        raise RuntimeError(f"Gemini API HTTP {response.status_code}: {detail}")
    result = response.json()
    candidates = result.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini non ha restituito candidati.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    parsed = extract_json(text)

    metadata = candidates[0].get("groundingMetadata") or {}
    grounded_sources: list[dict] = []
    for chunk in metadata.get("groundingChunks", []):
        web = chunk.get("web") or {}
        url = web.get("uri")
        title = web.get("title") or url
        if valid_http_url(url) and url not in {s["url"] for s in grounded_sources}:
            grounded_sources.append({"title": title, "url": url})
    queries = metadata.get("webSearchQueries") or []
    return parsed, grounded_sources, queries


def call_groq(api_key: str, gemini_result: dict, grounded_sources: list[dict]) -> dict:
    """Usa Groq per rifinire il JSON, senza permettere fonti fuori dal grounding Google."""
    system = (
        "Sei un redattore italiano. Restituisci esclusivamente JSON valido con le chiavi "
        "researchUpdates e sourceUpdates. Non aggiungere fatti, date, titoli o URL non "
        "presenti nell'input. Mantieni soltanto URL presenti nell'elenco delle fonti Google."
    )
    user = {
        "geminiResearch": gemini_result,
        "googleGroundedSources": grounded_sources,
        "requiredSchema": {
            "researchUpdates": [{"title": "", "summary": "", "date": "", "sources": [{"title": "", "url": ""}]}],
            "sourceUpdates": [{"title": "", "type": "film oppure serie", "year": 2027, "source": ""}]
        }
    }
    response = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        },
        timeout=TIMEOUT,
    )
    if not response.ok:
        raise RuntimeError(f"Groq API HTTP {response.status_code}: {response.text[:1200]}")
    choices = response.json().get("choices") or []
    if not choices:
        raise RuntimeError("Groq non ha restituito risposte.")
    return extract_json(choices[0].get("message", {}).get("content", ""))


def normalize(data: dict, ai: dict, grounded_sources: list[dict]) -> tuple[int, int]:
    # Allowlist: the AI may only emit source URLs actually returned by Google grounding.
    allowed = {s["url"]: s for s in grounded_sources}
    research = []
    for item in ai.get("researchUpdates", []):
        if not isinstance(item, dict) or not str(item.get("title", "")).strip():
            continue
        sources = []
        for source in item.get("sources", []):
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if url in allowed:
                sources.append({"title": str(source.get("title") or allowed[url]["title"])[:200], "url": url})
        if not sources:
            continue
        research.append({
            "title": str(item["title"]).strip()[:180],
            "summary": str(item.get("summary") or "").strip()[:700],
            "date": str(item.get("date") or "").strip()[:32],
            "sources": sources[:4],
        })
    # Deduplicate updates by title, preserving the freshest run's order.
    seen = set()
    cleaned_research = []
    for item in research:
        key = slug(item["title"])
        if key and key not in seen:
            seen.add(key)
            cleaned_research.append(item)

    existing = {
        slug(item.get("title", ""))
        for order in data.get("orders", {}).values()
        for section in order.get("sections", [])
        for item in section.get("items", [])
    }
    existing.update(slug(item.get("title", "")) for item in data.get("sourceUpdates", []))
    proposed = []
    for item in ai.get("sourceUpdates", []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:180]
        typ = str(item.get("type") or "").lower()
        year = item.get("year")
        source = item.get("source")
        if not title or typ not in {"film", "serie"} or not isinstance(year, int) or not 1930 <= year <= 2100:
            continue
        if not valid_http_url(source) or source not in allowed:
            continue
        key = slug(title)
        if not key or key in existing:
            continue
        existing.add(key)
        proposed.append({"title": title, "type": typ, "year": year, "source": source, "status": "da verificare"})
    # Keep recent results first and avoid unbounded growth.
    data["researchUpdates"] = cleaned_research[:12]
    data["sourceUpdates"] = proposed + [
        item for item in data.get("sourceUpdates", [])
        if slug(item.get("title", "")) not in {slug(x["title"]) for x in proposed}
    ]
    data["sourceUpdates"] = data["sourceUpdates"][:100]
    return len(data["researchUpdates"]), len(proposed)



def is_gemini_quota_error(exc: Exception) -> bool:
    """Riconosce l'esaurimento quota Gemini, distinto dagli errori applicativi."""
    message = str(exc).upper()
    return "GEMINI API HTTP 429" in message and (
        "RESOURCE_EXHAUSTED" in message
        or "EXCEEDED YOUR CURRENT QUOTA" in message
        or "QUOTA" in message
    )


def main() -> int:
    if not DATA_FILE.exists():
        print(f"ERRORE: file dati mancante: {DATA_FILE}", file=sys.stderr)
        return 1
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERRORE: catalogo JSON non valido: {exc}", file=sys.stderr)
        return 1
    if not data.get("orders", {}).get("marvel", {}).get("sections"):
        print("ERRORE: schema orders.marvel.sections mancante; non sovrascrivo il catalogo.", file=sys.stderr)
        return 1
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not gemini_key or not groq_key:
        missing = [name for name, value in (("GEMINI_API_KEY", gemini_key), ("GROQ_API_KEY", groq_key)) if not value]
        print("ERRORE: configura i secrets GitHub mancanti: " + ", ".join(missing), file=sys.stderr)
        return 1
    try:
        gemini_result, sources, queries = call_gemini(gemini_key, data)
        ai = call_groq(groq_key, gemini_result, sources)
        news_count, new_titles = normalize(data, ai, sources)
        data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        data["lastUpdate"] = {
            "status": "success",
            "model": MODEL + " + " + GROQ_MODEL,
            "sourceCount": len(sources),
            "searchQueries": queries[:10],
        }
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Aggiornamento completato: {news_count} notizie con fonti, {new_titles} nuovi titoli proposti, {len(sources)} fonti grounding.")
        return 0
    except Exception as exc:
        if is_gemini_quota_error(exc):
            # La quota Gemini è un limite esterno: non sovrascrivere i dati validi
            # e non bloccare la pubblicazione del sito con l'ultimo catalogo noto.
            data["lastUpdate"] = {
                "status": "quota_exceeded",
                "model": MODEL + " + " + GROQ_MODEL,
                "message": "Quota Gemini esaurita (HTTP 429). Aggiornamento AI rinviato; catalogo precedente mantenuto.",
            }
            DATA_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\\n",
                encoding="utf-8",
            )
            print(
                "AVVISO: quota Gemini esaurita (HTTP 429). "
                "Mantengo il catalogo esistente e continuo con la pubblicazione.",
                file=sys.stderr,
            )
            return 0
        print(f"ERRORE aggiornamento Gemini/Groq: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
