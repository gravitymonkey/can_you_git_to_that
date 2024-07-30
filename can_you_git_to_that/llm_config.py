import os
import tiktoken
import json
from jinja2 import Environment, FileSystemLoader

LLM_PRICING = {}

def _get_template_env():
    # Specify the templates directory
    file_loader = FileSystemLoader('can_you_git_to_that/prompts')
    env = Environment(loader=file_loader)
    return env

def get_prompt(template_name, prompt_props):
    env = _get_template_env()
    template = env.get_template(template_name)    
    prompt = template.render(prompt_props)
    return prompt

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

def init_cost_tracker(repo_parent, repo_name):
    filename = f"output/{repo_parent}-{repo_name}_cost_tracker.txt"
    global LLM_PRICING 
    LLM_PRICING = _load_pricing(filename)
    # read and total all the values
    total_cost_to_date = 0
    if os.path.exists(filename):
        f = open(filename, "r", encoding="utf-8")
        data = f.readlines()
        f.close()
        for row in data:
            row = row.strip()
            if not row.startswith("#"):
                cells = row.split("\t")
                #date model input output cost
                if len(cells) > 4:
                    total_cost_to_date += float(cells[4])
    else:
        f = open(filename, "w", encoding="utf-8")
        f.write("#date\tmodel\tinput\toutput\tcost\n")
        f.close()
    return total_cost_to_date
        
def _load_pricing(filename):
    with open('llm_pricing.json', encoding='utf-8') as f:
        data = json.load(f)
    pricing = {}
    pricing['logfile'] = filename
    pricing['prices'] = data
    return pricing

def get_LLM_pricing():
    return LLM_PRICING
