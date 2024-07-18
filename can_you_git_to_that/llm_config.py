
def get_base_url(ai_service):
    if ai_service == "ollama":
        return 'http://localhost:11434/v1'
    return 'https://api.openai.com/v1'

def get_key(ai_service):
    if ai_service == "ollama":
        return 'ollama'
    raise ValueError(f"Unknown AI service: {ai_service} - get key")
