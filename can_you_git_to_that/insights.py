from openai import OpenAI
import sqlite3
import json
from .llm_config import get_base_url, get_key, get_template_env


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
    env = get_template_env()
    template = env.get_template('author_commit_count_summary_system.txt')
    system = template.render()

    prompt_props = {"data": data}
    template = env.get_template('author_commit_count_summary_user.txt')
    prompt = template.render(prompt_props)

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
    return response.choices[0].message.content 