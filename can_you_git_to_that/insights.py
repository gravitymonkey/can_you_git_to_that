from openai import OpenAI
import sqlite3
import json
import hashlib
from .llm_config import get_base_url, get_key, get_prompt, num_tokens_from_string
from .llm import generate_summary
import logging
from datetime import datetime, timedelta

from collections import defaultdict

def generate_insights(repo_owner, repo_name, ai_model, start_date, end_date):
    ai_service, model = ai_model.split("|")
    summaries = [
        ("author-commits-summary", _get_author_commit_count, "author_commit_count_summary"),
        ("file-commit-count-summary", _get_file_commit_count, "file_commit_count_summary"),
        ("commit-count-by-date-summary", _get_commit_count_by_date, "commit_count_by_date_summary"),
        ("overall-tags-summary", _get_overall_tags, "overall_tags_summary"),
        ("tags-by-week-summary", _get_tags_by_week, "tags_by_week_summary"),
        ("churn-summary", _get_churn, "churn_summary"),
    ]

    for summary_name, data_func, summary_type in summaries:
        _generate_summary(repo_owner, repo_name, ai_service, model, start_date, end_date, summary_name, data_func, summary_type)

def _generate_summary(repo_owner, repo_name, ai_service, model, start_date, end_date, summary_name, data_func, summary_type):
    data = data_func(repo_owner, repo_name)
    data_hash = _generate_hash(data)
    
    if not _commit_hash_exists(summary_name, data_hash, repo_owner, repo_name):
        data_summary = generate_summary(summary_type, data, ai_service, model)
        _save_summary(summary_name, data_summary, repo_owner, repo_name, data_hash, ai_service, model, start_date, end_date)
    else:
        logging.info(f"{summary_name.replace('-', ' ').capitalize()} already exists with the same data")

def _get_overall_tags(repo_owner, repo_name):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
    cursor = conn.cursor()    
    
    query = '''
        SELECT t.name, SUM(ct.value) AS total_value
        FROM tags t
        JOIN commit_tags ct ON t.id = ct.tag_id
        GROUP BY t.name
        ORDER BY total_value DESC
    '''

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    rows = []
    for row in results:
        row_data = {    "tag": row[0], 
                        "total_value": row[1]
                    }
        rows.append(row_data)
    return json.dumps(rows, indent=4)

def _get_tags_by_week(repo_owner, repo_name):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
    cursor = conn.cursor()    

    query = '''
            SELECT t.name, ct.value, c.timestamp
            FROM tags t
            JOIN commit_tags ct ON t.id = ct.tag_id
            JOIN commits c ON ct.commit_id = c.id
        '''

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    data = defaultdict(lambda: defaultdict(int))

    for tag, value, commit_timestamp in rows:
        commit_datetime = datetime.fromtimestamp(commit_timestamp)
        year, week, _ = commit_datetime.isocalendar()
        week_str = f"{year}-{week:02d}"
        data[week_str][tag] += value

    # Ensure all weeks are included
    since_date = min(datetime.fromtimestamp(row[2]) for row in rows)
    current_date = datetime.now()
    week_list = []
    while since_date <= current_date:
        year, week, _ = since_date.isocalendar()
        week_list.append(f"{year}-{week:02d}")
        since_date += timedelta(weeks=1)

    result = []
    for week in week_list:
        year, xweek = map(int, week.split('-'))
        first_day_of_week = datetime.strptime(f'{year}-W{xweek-1}-1', "%Y-W%U-%w").date()        
        week_of = first_day_of_week + timedelta(days=(0 - first_day_of_week.weekday()))        
        sweek_of = week_of.strftime("%Y-%m-%d")
        result.append({
            "week": week,
            "week_starting": sweek_of,
            "tags": data[week]
        })

    all_tags = set()
    for week in result:
        sum_values = sum(week['tags'].values())
        for tag in week['tags']:
            all_tags.add(tag)
            raw = round(week['tags'][tag], 2)
            perc = round((week['tags'][tag]/sum_values)*100, 2)
            week['tags'][tag] = {
                "raw": raw,
                "percentage": perc
            }
    tag_track = {}
    all_tags = list(all_tags)
    all_tags.sort()
    for tag in list(all_tags):
        week_data = []
        for week in result:
            if tag in week['tags']:
                week_data.append(week['tags'][tag]['percentage'])
            else:
                week_data.append(0)
        tag_track[tag] = week_data

    full_result = {}
    full_result['percentage_by_tag_per_week'] = tag_track
    full_result['by_week'] = result

    return json.dumps(full_result, indent=4)

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

def _get_churn(repo_owner, repo_name):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
    cursor = conn.cursor()    
    cursor.execute("""
        SELECT filename, SUM(churn_count) AS total_churn
        FROM commits where description is not null
        GROUP BY filename
    """)
    churn_data = cursor.fetchall()

    # Convert the query result to a dictionary
    data = {}
    for item in churn_data:
        filename = item[0]
        total_churn = item[1]
        path = filename.split('/')
        current = data
        for part in path[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[path[-1]] = total_churn

    # Recursive function to build the JSON structure
    def build_hierarchy(d, depth=0):
        result = []
        for key, value in d.items():
            if isinstance(value, dict):
                result.append({
                    "folder_name": key,
                    "children": build_hierarchy(value, depth + 1),
                })
            else:
                result.append({
                    "file_name": key,
                    "churn": value,
                })
        return result
    # Build the final JSON structure
    json_data = {
        "repo_name": repo_name,
        "children": build_hierarchy(data)
    }

    return json.dumps(json_data, indent=4)

def _save_summary(which, summary, repo_owner, repo_name, data_hash, ai_service, ai_model, start_date, end_date):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO summaries (name, hash, ai_service, ai_model, summary, start_date, end_date, createdAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (which, data_hash, ai_service, ai_model, summary, start_date, end_date))

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
