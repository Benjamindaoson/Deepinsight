"""Local model configuration; no secrets in code or evidence."""
import json
from pathlib import Path
from agno.models.openai import OpenAIChat

ROOT = Path(__file__).resolve().parents[2]

def model():
    c = json.loads((ROOT / 'secrets/model.json').read_text(encoding='utf-8-sig'))
    return OpenAIChat(id=c['model'], api_key=c['api_key'], base_url=c['base_url'],
                      max_tokens=512, timeout=60, max_retries=0)
