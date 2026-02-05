"""LLM trade confidence assessment endpoints."""

from fastapi import APIRouter

from config import settings
from src.api.schemas import LLMStatusResponse

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/status", response_model=LLMStatusResponse)
def llm_status():
    providers = []
    if settings.ANTHROPIC_API_KEY:
        providers.append("anthropic")
    if settings.OPENAI_API_KEY:
        providers.append("openai")
    if settings.XAI_API_KEY:
        providers.append("grok")

    return LLMStatusResponse(
        enabled=settings.LLM_ENABLED,
        threshold=settings.LLM_CONFIDENCE_THRESHOLD,
        timeout=settings.LLM_TIMEOUT,
        providers=providers,
    )
