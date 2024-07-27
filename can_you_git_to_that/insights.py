from openai import OpenAI
import sqlite3
import json
import hashlib
from .llm_config import get_base_url, get_key, get_prompt, num_tokens_from_string
import logging
from datetime import datetime

def generate_insights(repo_owner, repo_name, ai_model):
    ai_service = ai_model.split("|")[0]
    model = ai_model.split("|")[1]
    _generate_author_commit_count_summary(repo_owner, repo_name, ai_service, model)
    _generate_file_commit_count_summary(repo_owner, repo_name, ai_service, model)   
    _generate_commit_count_by_date_summary(repo_owner, repo_name, ai_service, model)

def _generate_author_commit_count_summary(repo_owner, repo_name, ai_service, model):
    author_data = _get_author_commit_count(repo_owner, repo_name)
    author_data_hash = _generate_hash(author_data) #author_data should be json string
    if not _commit_hash_exists("author-commits-summary", author_data_hash, repo_owner, repo_name):
        author_data_summary = _generate_summary("author_commit_count_summary", author_data, ai_service, model)
        _save_summary("author-commits-summary", author_data_summary, repo_owner, repo_name, author_data_hash)
    else:
        logging.info("Author commit count summary already exists for author-commits-summary with same author data")

def _generate_file_commit_count_summary(repo_owner, repo_name, ai_service, model):   
    file_data = _get_file_commit_count(repo_owner, repo_name)
    file_data_hash = _generate_hash(file_data) 
    if not _commit_hash_exists("file-commit-count-summary", file_data_hash, repo_owner, repo_name):
        file_data_summary = _generate_summary("file_commit_count_summary", file_data, ai_service, model)
        _save_summary("file-commit-count-summary", file_data_summary, repo_owner, repo_name, file_data_hash)
    else:
        logging.info("Author commit count summary already exists for author-commits-summary with same author data")


def _generate_commit_count_by_date_summary(repo_owner, repo_name, ai_service, model):
    commit_data = _get_commit_count_by_date(repo_owner, repo_name)
    commit_data_hash = _generate_hash(commit_data) 
    print(commit_data_hash)
    if not _commit_hash_exists("commit-count-by-date-summary", commit_data_hash, repo_owner, repo_name):
        commit_data_summary = _generate_summary("commit_count_by_date_summary", commit_data, ai_service, model)
        _save_summary("commit-count-by-date-summary", commit_data_summary, repo_owner, repo_name, commit_data_hash)
    else:
        logging.info("Commit count by date summary already exists for commit-counts-by-date-summary with same commit data")


def _get_file_commit_count(repo_owner, repo_name):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
    cursor = conn.cursor()    
    
    query = """
        SELECT filename, COUNT(DISTINCT commit_hash) as commit_count
        FROM commits
        GROUP BY filename
        ORDER BY commit_count DESC;
    """

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    rows = []
    for row in results:
        row_data = {    "filename": row[0], 
                        "commit_count": row[1]
                    }
        rows.append(row_data)
    
    return json.dumps(rows, indent=4)


def _get_commit_count_by_date(repo_parent, repo_name):
    conn = sqlite3.connect(f"output/{repo_parent}-{repo_name}.db")
    cursor = conn.cursor()    
    
    query = """
        SELECT date, commit_hash, filename
        FROM commits
    """

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    today = datetime.today().date()
    track = {}
    filetrack = {}
    for row in results:
        commit_date = datetime.strptime(row[0], '%Y-%m-%dT%H:%M:%S').date()
        chash = row[1]
        filename = row[2]
        if commit_date not in track:
            track[commit_date] = set()
        track[commit_date].add(chash)
        if chash not in filetrack:
            filetrack[chash] = set()
        filetrack[chash].add(filename)
            
    rows = []
    dates = list(track.keys())
    dates.sort()
    for d in dates:
        commit_date = d
        days_before_today = (today - commit_date).days
        filecount = 0
        for hashes in track[d]:
            filecount += len(filetrack[hashes])
        row_data = {    "date": str(d), 
                        "commit_count": len(track[d]),
                        "file_count": filecount,
                        "days_ago": days_before_today
                    }
        rows.append(row_data)
    
    return json.dumps(rows, indent=4)   


def _save_summary(which, summary, repo_owner, repo_name, data_hash):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO summaries (name, hash, summary, createdAt)
        VALUES (?, ?, ?, datetime('now'))
    ''', (which, data_hash, summary))

    conn.commit()
    conn.close()

def _commit_hash_exists(which_name, summary_hash, repo_owner, repo_name):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COUNT(*) FROM summaries
        WHERE name = ? AND hash = ?
    ''', (which_name, summary_hash))

    result = cursor.fetchone()
    conn.close()

    if result is None:
        return False
    if result[0] == 0:
        return False
    return True



def _generate_hash(input_string):
    return hashlib.md5(input_string.encode()).hexdigest()


def _get_author_commit_count(repo_parent, repo_name):
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
    rows = []    
    for row in result:
        row_data = {    "author": row[0], 
                        "total_file_commits": row[1],
                        "first_commit_date": row[2],
                        "last_commit_date": row[3],
                    }
        rows.append(row_data)
    
    return json.dumps(rows, indent=4)    

def _generate_summary(which, data, service_name, model_name):
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
    return response.choices[0].message.content 