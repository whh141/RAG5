import os

import json
import torch
from dotenv import load_dotenv

load_dotenv()

# device config
EMBEDDING_DEVICE = "cuda" if torch.cuda.is_available(
) else "mps" if torch.backends.mps.is_available() else "cpu"
LLM_DEVICE = "cuda" if torch.cuda.is_available(
) else "mps" if torch.backends.mps.is_available() else "cpu"
num_gpus = torch.cuda.device_count()

# model cache config
MODEL_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'model_cache')


# vector storage config
VECTOR_STORE_PATH='./vector_store'
COLLECTION_NAME='my_collection'


# llm backend config
DEF_BACKEND = "vllm"
LLM_BACKEND = os.environ.get("LLM_BACKEND", DEF_BACKEND).strip().lower() or DEF_BACKEND

def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_MAX_WORKERS = _safe_int(os.environ.get("OLLAMA_MAX_WORKERS", "1"), 1)
OLLAMA_TIMEOUT = _safe_int(os.environ.get("OLLAMA_TIMEOUT", "900"), 900)


def _parse_options(options_env: str):
    if not options_env:
        return None
    try:
        return json.loads(options_env)
    except json.JSONDecodeError:
        return None


OLLAMA_OPTIONS = _parse_options(os.environ.get("OLLAMA_OPTIONS"))

# ============================================================
# 基础 LLM OpenAI API 配置 (用于 RAG)
# LLM_BACKEND="openai" 时使用
# ============================================================
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-3.5-turbo")

# ============================================================
# 嵌入模型配置
# ============================================================
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "local").strip().lower()
EMBEDDING_MODEL_PATH = os.environ.get("EMBEDDING_MODEL_PATH", "./pre_train_model/m3e-large")

# API 嵌入模型配置
EMBEDDING_API_TYPE = os.environ.get("EMBEDDING_API_TYPE", "openai").strip().lower()  # "openai" 或 "jina"
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "")
EMBEDDING_API_BASE = os.environ.get("EMBEDDING_API_BASE", "")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "text-embedding-v1")

# Ollama 嵌入模型配置
OLLAMA_EMBEDDING_BASE_URL = os.environ.get("OLLAMA_EMBEDDING_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

# ============================================================
# Rerank 模型配置
# ============================================================
RERANK_BACKEND = os.environ.get("RERANK_BACKEND", "local").strip().lower()
RERANK_API_PROVIDER = os.environ.get("RERANK_API_PROVIDER", "jina").strip().lower()
RERANK_MODEL_PATH = os.environ.get("RERANK_MODEL_PATH", "./pre_train_model/bge-reranker-large")
RERANK_API_KEY = os.environ.get("RERANK_API_KEY", "")
RERANK_API_BASE = os.environ.get("RERANK_API_BASE", "")
RERANK_MODEL_NAME = os.environ.get("RERANK_MODEL_NAME", "bge-reranker-v2-m3")
RERANK_TOP_N = _safe_int(os.environ.get("RERANK_TOP_N", "10"), 10)

# ============================================================
# 评分模型配置 (test_score.py 使用)
# ============================================================
SCORING_BACKEND = os.environ.get("SCORING_BACKEND", "local").strip().lower()
SCORING_MODEL_PATH = os.environ.get("SCORING_MODEL_PATH", "./pre_train_model/text2vec-base-chinese")
SCORING_DEVICE = os.environ.get("SCORING_DEVICE", "cuda:0")
SCORING_API_TYPE = os.environ.get("SCORING_API_TYPE", "openai").strip().lower()
SCORING_API_KEY = os.environ.get("SCORING_API_KEY", "")
SCORING_API_BASE = os.environ.get("SCORING_API_BASE", "https://api.openai.com/v1")
SCORING_MODEL_NAME = os.environ.get("SCORING_MODEL_NAME", "text-embedding-3-small")

