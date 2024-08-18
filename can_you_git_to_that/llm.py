from openai import OpenAI
import json
import logging
import datetime
from .llm_config import get_base_url, get_key, num_tokens_from_string, get_prompt, get_LLM_pricing

SESSION_COST = 0.0
        
def summarize_diff(filename, diff, file_sample, ai_service, ai_model):
    """
    Summarizes the difference between two files or the content of a single file.

    Args:
        filename (str): The name of the file being summarized.
        diff (str): The standard git diff between two files. If None, the file content will be used instead.
        file_sample (str): The content of the file being summarized.
        ai_service (str): The AI service being used.
        ai_model (str): The AI model being used.

    Returns:
        str: The summarized difference.

    """
    system = get_prompt('summarize_diff_system.txt', {})

    clause = "Unified Diff:"
    data = diff
    if diff is None:
        clause = "File Content:"
        data = file_sample

    user_prompt_prompts = {"filename": filename, "clause": clause, "data": data}
    prompt = get_prompt('summarize_diff_user.txt', user_prompt_prompts)
    
    num_tokens = num_tokens_from_string(prompt)
    
    logging.info("summarize diff has prompt w/num tokens: %s", num_tokens)

    client = OpenAI(
        base_url = get_base_url(ai_service),
        api_key= get_key(ai_service),
    )
    response = client.chat.completions.create(
        model=ai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2
    )
    _track_LLM_cost(response, ai_service, ai_model)
    return response.choices[0].message.content.strip()

def shorter_summarize_diff(filename, long_summary, ai_service, ai_model):
    system = get_prompt('shorter_summarize_diff_system.txt', {})

    user_prompt_data = {"filename": filename, "long_summary": long_summary}
    prompt = get_prompt('shorter_summarize_diff_user.txt', user_prompt_data)

    num_tokens = num_tokens_from_string(prompt)
    logging.info("shorter_summarize_diff has prompt w/num tokens: %s", num_tokens)

    client = OpenAI(
        base_url = get_base_url(ai_service),
        api_key= get_key(ai_service),
    )
    response = client.chat.completions.create(
        model=ai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4
    )
    _track_LLM_cost(response, ai_service, ai_model)
    return response.choices[0].message.content.strip()

def classify_description(tags, desc, ai_service, ai_model):

    system = get_prompt('classify_description_system.txt', {"tags":tags})

    props = {"description": desc}
    prompt = get_prompt('classify_description_user.txt', props)

    num_tokens = num_tokens_from_string(prompt)

    logging.info("classify description has prompt w/num tokens: %s", num_tokens)
    client = OpenAI(
        base_url = get_base_url(ai_service),
        api_key= get_key(ai_service),
    )
    model = ai_model
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2
    )
    _track_LLM_cost(response, ai_service, ai_model)    
    return response.choices[0].message.content 

def summarize_pr(prs, ai_service, ai_model):

    system = get_prompt('summarize_pr_system.txt', {})

    prompt = get_prompt('summarize_pr_user.txt', {"prs": prs})

    num_tokens = num_tokens_from_string(prompt)
    logging.info("summarize pr has prompt w/num tokens: %s", num_tokens)

    client = OpenAI(
        base_url = get_base_url(ai_service),
        api_key= get_key(ai_service),
    )
    model = ai_model
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2
    )
    _track_LLM_cost(response, ai_service, ai_model)
    return response.choices[0].message.content 


def describe_code(func_name, func_code, filename, ai_service, ai_model):
    system = get_prompt('describe_code_system.txt', {})

    prompt = get_prompt('describe_code_user.txt', {"code": func_code, "func_name": func_name, "filename": filename})  

    num_tokens = num_tokens_from_string(prompt)
    logging.info("describe code has prompt w/num tokens: %s", num_tokens)

    client = OpenAI(
        base_url = get_base_url(ai_service),
        api_key= get_key(ai_service),
    )
    model = ai_model
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1
    )
    _track_LLM_cost(response, ai_service, ai_model)
    return response.choices[0].message.content 


def rate_code(func_name, func_code, filename, ai_service, ai_model):
    system = get_prompt('rate_code_system.txt', {})

    prompt = get_prompt('rate_code_user.txt', {"code": func_code, "func_name": func_name, "filename": filename})  

    num_tokens = num_tokens_from_string(prompt)
    logging.info("rate code has prompt w/num tokens: %s", num_tokens)

    client = OpenAI(
        base_url = get_base_url(ai_service),
        api_key= get_key(ai_service),
    )
    model = ai_model
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1
    )
    _track_LLM_cost(response, ai_service, ai_model)
    return response.choices[0].message.content 


def generate_summary(which, data, service_name, model_name):
    system = get_prompt(f'{which}_system.txt', {})

    prompt_props = {"data": data}
    prompt = get_prompt(f'{which}_user.txt', prompt_props)

    num_tokens = num_tokens_from_string(prompt)
    logging.info("insights generate summary has prompt w/num tokens: %s", num_tokens)

    client = OpenAI(
        base_url = get_base_url(service_name),
        api_key= get_key(service_name),
    )
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2
    )
    _track_LLM_cost(response, service_name, model_name)
    return response.choices[0].message.content 

def _track_LLM_cost(response, service_name, model_name):
    llm_pricing = get_LLM_pricing()
    try:
        pricing = llm_pricing['prices'][service_name][model_name]
        if response.usage is not None:
            output_tokens = response.usage.completion_tokens
            total = (output_tokens/1000000) * float(pricing['output'])
            input_tokens = response.usage.prompt_tokens
            total += (input_tokens/1000000) * float(pricing['input'])
            global SESSION_COST
            SESSION_COST += total
            logging.info("LLM total session cost: $%s", SESSION_COST)
            _log_LLM_cost(llm_pricing['logfile'], service_name, model_name, input_tokens, output_tokens, total)

    except Exception as ee:
        logging.error("Error tracking LLM cost: %s", ee)
        logging.error("got service name %s and model name %s", service_name, model_name)
        logging.error("llm pricing: %s", llm_pricing)
        logging.error("response: %s", response)
        return    
    
def _log_LLM_cost(logfile, service, model, num_input, num_output, cost):
    try:
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()}\t{service}-{model}\t{num_input}\t{num_output}\t{cost}\n")
    except Exception as ee:
        logging.error("Error logging LLM cost: %s", ee)
