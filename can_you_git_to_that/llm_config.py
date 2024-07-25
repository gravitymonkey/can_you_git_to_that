import os
import tiktoken
from jinja2 import Environment, FileSystemLoader

def get_template_env():
    # Specify the templates directory
    file_loader = FileSystemLoader('can_you_git_to_that/prompts')
    env = Environment(loader=file_loader)
    return env

def get_base_url(ai_service):
    if ai_service == "ollama":
        return 'http://localhost:11434/v1'
    elif ai_service == "openai":
        return 'https://api.openai.com/v1'
    raise ValueError(f"Unknown AI service: {ai_service} - get base url")

def get_key(ai_service):
    if ai_service == "ollama":
        return 'ollama'
    elif ai_service == "openai":
        env = os.environ.get("OPENAI_API_KEY")
        return env
    raise ValueError(f"Unknown AI service: {ai_service} - get key")

def num_tokens_from_string(value):
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(value))
    return num_tokens


