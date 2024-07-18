from openai import OpenAI
import sqlite3
import json
from .llm_config import get_base_url, get_key


def get_author_commit_count(repo_parent, repo_name):
    conn = sqlite3.connect(f"output/{repo_parent}-{repo_name}.db")
    cursor = conn.cursor()    
    
    query = """
    SELECT author,
        COUNT(*) as total_commits,
        MIN(date) as first_commit_date,
        MAX(date) as last_commit_date
    FROM 
        commits
    GROUP BY 
        author
    ORDER BY 
        total_commits DESC
    """

    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    print(result)
    rows = []    
    for row in result:
        row_data = {    "author": row[0], 
                        "total_file_commits": row[1],
                        "first_commit_date": row[2],
                        "last_commit_date": row[3],
                    }
        rows.append(row_data)
    
    return json.dumps(rows, indent=4)    

def get_author_commit_count_summary(data, service_name, model_name):
    system = """
        You are a helpful and experienced software engineering leader.
        You provide practical, useful information about the code and output of your team,
        and reflect upon the implications of the provided developer git data on how your team
        is currently functioning, and how to improve, as well as how to reduce risk
        for the future.
    """

    prompt = """
        You received the follow data which lists every author who 
        committed code to the repo, along with the total number of
        commits, over the repo's history, and the first and last
        date of their commit history, which informs you about their
        time and tenure of their contributions.  Describe the data in a 
        manner that is useful for a non-technical stakeholder.
        Avoid technical jargon, and focus on the high level implications.
        Avoid judgement about individual developer quality or performance.
        Observe trends and changes in the data, but do not make predictions.

        Provide you commentary as a single paragraph, and avoid lists or bullet points.
        \n\n
        """ 
    prompt += data

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
        temperature=0.3
    )
    return response.choices[0].message.content 