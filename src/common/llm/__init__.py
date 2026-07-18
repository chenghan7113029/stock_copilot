"""common.llm 包：LLM 叙事基建。"""

from common.llm.client import LLMClient
from common.llm.models import ChatResult, NarrateResult
from common.llm.narrator import NarrateCache, compute_cache_key, narrate

__all__ = [
    "ChatResult",
    "LLMClient",
    "NarrateCache",
    "NarrateResult",
    "compute_cache_key",
    "narrate",
]
