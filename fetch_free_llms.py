import aiohttp
from typing import List, Tuple
from env_loader import env_loader

async def fetch_free_llms(only_free: bool = True) -> List[Tuple[str, str]]:
    api_key = env_loader.get('OPENROUTER_API_KEY')
    if not api_key:
        default_llms = env_loader.get_list('FREE_LLMS_DEFAULT')
        return [(llm, llm) for llm in default_llms]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://openrouter.ai/api/v1/models',
                headers={'Authorization': f'Bearer {api_key}'}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = []

                    for model in data.get('data', []):
                        model_id = model.get('id', '')
                        pricing = model.get('pricing', {})

                        if only_free:
                            prompt_cost = float(pricing.get('prompt', '0'))
                            completion_cost = float(pricing.get('completion', '0'))

                            if prompt_cost == 0 and completion_cost == 0:
                                models.append((model_id, model.get('name', model_id)))
                        else:
                            models.append((model_id, model.get('name', model_id)))

                    return models if models else [(llm, llm) for llm in env_loader.get_list('FREE_LLMS_DEFAULT')]
    except Exception as e:
        print(f"Error fetching models: {e}")

    default_llms = env_loader.get_list('FREE_LLMS_DEFAULT')
    return [(llm, llm) for llm in default_llms]
