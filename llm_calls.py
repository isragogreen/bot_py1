import aiohttp
import asyncio
import uuid
from env_loader import get_env
from error_handler import log_error

# Чтение параметров из .env один раз
OPENROUTER_API_KEY = get_env("OPENROUTER_API_KEY")
OPENROUTER_URL = get_env("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")

PROMPT_ROLE_FILE = get_env("PROMPT_ROLE", "prompt_role.txt")
PROMPT_SCORE_ROLE_FILE = get_env("PROMPT_SCORE_ROLE", "prompt_score_role.txt")
PROMPT_RESPONSE_FILE = get_env("PROMPT_RESPONSE", "prompt_response.txt")
PROMPT_SCORE_RESPONSE_FILE = get_env("PROMPT_SCORE_RESPONSE", "prompt_score_response.txt")

MAX_TOKENS_ROLE = int(get_env("MAX_TOKENS_ROLE", 64))
MAX_TOKENS_SCORE_ROLE = int(get_env("MAX_TOKENS_SCORE_ROLE", 32))
MAX_TOKENS_RESPONSE = int(get_env("MAX_TOKENS_RESPONSE", 128))
MAX_TOKENS_SCORE_RESPONSE = int(get_env("MAX_TOKENS_SCORE_RESPONSE", 32))
TIMEOUT = int(get_env("LLM_TIMEOUT", 30))

def _read_prompt(filename):
    try:
        with open(filename, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log_error(e, "llm_calls._read_prompt")
        return ""

PROMPT_ROLE = _read_prompt(PROMPT_ROLE_FILE)
PROMPT_SCORE_ROLE = _read_prompt(PROMPT_SCORE_ROLE_FILE)
PROMPT_RESPONSE = _read_prompt(PROMPT_RESPONSE_FILE)
PROMPT_SCORE_RESPONSE = _read_prompt(PROMPT_SCORE_RESPONSE_FILE)

async def _call_llm_async(model, prompt, max_tokens, request_id=None):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens
            }
            if request_id:
                payload["request_id"] = request_id
            async with session.post(OPENROUTER_URL, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return {
                    "request_id": request_id,
                    "model": model,
                    "response": data["choices"][0]["message"]["content"]
                }
    except Exception as e:
        log_error(e, "llm_calls._call_llm_async")
        return {
            "request_id": request_id,
            "model": model,
            "response": ""
        }

async def determine_role_llm(message, model, roles_dict):
    prompt = PROMPT_ROLE.format(
        message=message,
        model=model,
        roles="\n".join([f"{r}: {desc}" for r, desc in roles_dict.items()])
    )
    request_id = str(uuid.uuid4())
    return await _call_llm_async(model, prompt, MAX_TOKENS_ROLE, request_id)

async def score_role_choice_llm(llm_result, roles_dict, model, message):
    prompt = PROMPT_SCORE_ROLE.format(
        llm_result=llm_result,
        roles="\n".join([f"{r}: {desc}" for r, desc in roles_dict.items()]),
        model=model,
        message=message
    )
    request_id = str(uuid.uuid4())
    return await _call_llm_async(model, prompt, MAX_TOKENS_SCORE_ROLE, request_id)

async def generate_response_llm(message, model, role, roles_dict):
    prompt = PROMPT_RESPONSE.format(
        message=message,
        model=model,
        role=role,
        roles="\n".join([f"{r}: {desc}" for r, desc in roles_dict.items()])
    )
    request_id = str(uuid.uuid4())
    return await _call_llm_async(model, prompt, MAX_TOKENS_RESPONSE, request_id)

async def score_response_llm(response, model, role, message, roles_dict):
    prompt = PROMPT_SCORE_RESPONSE.format(
        response=response,
        model=model,
        role=role,
        message=message,
        roles="\n".join([f"{r}: {desc}" for r, desc in roles_dict.items()])
    )
    request_id = str(uuid.uuid4())
    return await _call_llm_async(model, prompt, MAX_TOKENS_SCORE_RESPONSE, request_id)