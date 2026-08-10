from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .config import settings
from .schemas import ExtractionProposal
from .services import search_records


SAFETY_SYSTEM = """You are HealthVault Local's organization assistant, not a clinician. Use only the supplied personal records. Never diagnose, prescribe, change dosage, or infer illegible medical instructions. Unknown values must be null. Cite supporting record UUIDs. If evidence is absent, say so plainly."""


async def ollama_status() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
        selected = settings.ollama_model or (models[0].get("name") if models else None)
        return {"available": True, "provider": "ollama", "selected_model": selected, "models": [{"name": model.get("name"), "size": model.get("size")} for model in models]}
    except Exception:
        return {"available": False, "provider": "ollama", "selected_model": settings.ollama_model, "models": [], "message": "Ollama is not running. All non-AI features remain available."}


async def _generate(prompt: str, *, json_mode: bool = False) -> str:
    status = await ollama_status()
    model = status.get("selected_model")
    if not status["available"] or not model:
        raise HTTPException(status_code=503, detail="Local AI is unavailable. Install Ollama and a model, then select it in Settings.")
    body: dict[str, Any] = {"model": model, "prompt": prompt, "system": SAFETY_SYSTEM, "stream": False, "options": {"temperature": 0}}
    if json_mode:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{settings.ollama_url}/api/generate", json=body)
        response.raise_for_status()
        return str(response.json().get("response", ""))


async def answer_from_records(db: Session, question: str, profile_id: str | None) -> dict[str, Any]:
    evidence = search_records(db, question, profile_id=profile_id, limit=12)
    if not evidence:
        return {"answer": "I could not find supporting information in the stored records.", "citations": []}
    prompt = f"Question: {question}\n\nRecords (JSON):\n{json.dumps(evidence, ensure_ascii=False)}\n\nAnswer concisely using only these records. Add citations as [record:UUID]."
    answer = await _generate(prompt)
    return {"answer": answer, "citations": evidence}


async def extract_medical_text(text: str) -> ExtractionProposal:
    prompt = f"""Extract organization candidates from the source below. Return strict JSON with keys patient, visit, symptoms, diagnosis_text, medications, tests, follow_up, uncertain_fields, confidence. Every non-null extracted field object should include value, confidence (0-1), source_text, verification_status='unverified'. Do not guess. For unreadable or uncertain medicine text use null and list it in uncertain_fields.\n\nSOURCE:\n{text[:30000]}"""
    raw = await _generate(prompt, json_mode=True)
    try:
        return ExtractionProposal.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="The local model returned malformed structured output; no records were changed.") from exc


async def transcribe_voice(path: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Local voice transcription is not installed. The original recording is safely stored.") from exc
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(path, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()
