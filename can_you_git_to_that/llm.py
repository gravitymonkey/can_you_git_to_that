from openai import OpenAI
import sqlite3
import json
import logging
from .llm_config import get_base_url, get_key, num_tokens_from_string, get_prompt

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
    return response.choices[0].message.content 