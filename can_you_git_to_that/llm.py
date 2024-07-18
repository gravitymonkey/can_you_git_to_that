from openai import OpenAI
import sqlite3
import json
from .llm_config import get_base_url, get_key


def summarize_diff(filename, diff, file_sample, ai_service, ai_model):
    clause = "Unified Diff:"
    data = diff
    if diff is None:
        clause = "File Content:"
        data = file_sample
        

    system = """
    You are a talented developer just getting familiar with this codebase, 
    provide a summary of the changes in the following diff (provided in 
    unified format) or file content, in a short and succinct single sentence. DO NOT GO INTO DETAIL. 
    DO NOT INCLUDE CODE SAMPLES, DO NOT SUGGEST IMPROVEMENTS OR CHANGES.
    DO NOT GUESS ABOUT FUNCTIONALITY BASED ON VARIABLE NAMES, OR STRUCTURE,
    ONLY DESCRIBE BASED ON WHAT YOU CAN SEE.
    If the diff is large or incomplete, focus on the high level changes.
    Focus on the functional changes this will provide, along with relevant 
    high level technical or implementation changes.  
    """
    prompt = f"File: {filename}\n{clause}\n\n{data}\n"
    
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
    system = """
    You are a senior developer who has received the attached plain language
    summary of this commit from a junior developer.  Rewrite it to be a 
    very brief summary and overview.  DO NOT GO INTO DETAIL.  DO NOT RECOMMEND CHANGES.
    DO NOT INCLUDE CODE SAMPLES. Drop phrases like "it looks like" or "you're trying to".
    Simplify format to remove unnecessary lists and line breaks, a single sentence is ideal.
    If the summary is too large or incomplete, focus on the high level changes. 
    You're not trying to impress someone with your expertise, you're merely 
    attempting to document the changes in a clear and concise manner for a product-focused user.
    """
    prompt = f"File: {filename}\nJunior Developer Summary:\n\n{long_summary}\n"

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
    system = """
    You are a helpful and knowledgeable assistant. 
    Your task is to classify edit descriptions of code changes 
    into one or more of the following categories: 
    """
    categories = "\n"
    for tag in tags:
        categories = categories + "\t" + tag + "\n"

    system += categories

    system += """

        Consider the edit description provided and classify it 
        into the most appropriate categories from the list above, 
        followed by a weight from 0 to 10.  Each category must have
        it's own weight, and the sum of all weights should be 10.
        YOUR SELECTION(S) MUST COME FROM THE LIST OF CATEGORIES PROVIDED.
        DO NOT EXPLAIN YOUR REASONING. DO NOT SUGGEST CHANGES. 
        Respond with the category(s) name in a comma-separated format.

        **Example 1:**
        Description: "Fixed a bug causing crashes when the user clicks the save button."
        Response: Bug_Fix,10

        **Example 2:**
        Description: "Updated the CSS styles for the homepage to improve the layout on mobile devices."
        Response: Style_CSS,5,Frontend,5

        **Example 3:**
        Description: "Added new endpoints with documentation to the API for user authentication."
        Response: API,5,Authentication,3,Documentation,2

    """
    prompt = f"Description: {desc}\n"

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

