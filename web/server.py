# app.py
import sqlite3
import math
import glob
import os
import re
from collections import namedtuple, defaultdict
from datetime import datetime, timedelta
from isoweek import Week
import pprint as pp

from flask import Flask, request, jsonify, send_from_directory, render_template

app = Flask(__name__, static_url_path='', static_folder='static')

COLORS = ['#465659', '#7CA2A6', '#172626', '#D98943', '#D9A78B', '#59696D', '#8CD0B6']

@app.route('/')
def serve_index():
    repos = []
    for db_file in glob.glob('../output/*.db'):
        repo_name = os.path.basename(db_file).replace('.db', '')
        repo_name = repo_name.replace('-', '/', 1)
        print(repo_name)
        repos.append(repo_name)
    return render_template('index.html', repos=repos)



@app.route('/<repo_parent>/<repo_name>')
def serve_repo(repo_parent, repo_name):
    print("serve_repo", repo_parent, repo_name)
    if repo_parent == 'static':
        print("send from directory", app.static_folder)
        return send_from_directory(app.static_folder, repo_name)

    # Capture query string parameters
    query_params = request.args.to_dict()
    if 'startAt' in query_params:
        startAt = query_params['startAt'] 
    else:
        args = {
            'repo_parent': repo_parent,
            'repo_name': repo_name
        }
        startAt = _get_first_commit_date(args)
    endAt = _get_last_run(repo_parent, repo_name)
    
    print(startAt, endAt)
    return render_template('default.html',    
                            repo_parent=repo_parent, 
                            repo_name=repo_name,
                            startAt=startAt,
                            endAt=endAt)

@app.route('/author-commits', methods=['GET'])
def get_data():
    request_args = request.args.to_dict()
    since = request_args.get('startAt', None)
    author_data = query_contributions_by_author(request_args, since=since)
    data = []
    for author, num_commits in author_data:
        data.append({"author": author, "commits": num_commits})
    return jsonify(data)

@app.route('/file-changes', methods=['GET'])
def get_file_changes_data():
    request_args = request.args.to_dict()
    since = request_args.get('startAt', None)
    file_data = get_changes_by_file(request_args, since=since)
    data = []
    for author, num_commits in file_data:
        data.append({"filename": author, "commits": num_commits})
    return jsonify(data)


@app.route('/commits-over-time', methods=['GET'])
def get_commits_over_time_data():
    request_args = request.args.to_dict()
    since = request_args.get('startAt', None)
    file_data = get_contributions_over_time_by_week(request_args, since=since)
    
    # Assuming file_data is a list of tuples in the format [(year-week, num_commits), ...]
    data_dict = {date_str: num_commits for date_str, num_commits in file_data}
    
    # Determine the date range
    if since:
        start_date = datetime.strptime(since, '%m/%d/%Y')        
    else:
        # Parse the first date string in the data_dict keys
        first_date_str = min(data_dict.keys())
        year, week = map(int, first_date_str.split('-'))
        start_date = Week(year, week).monday()
    
    # Parse the last date string in the data_dict keys
    last_date_str = max(data_dict.keys())
    year, week = map(int, last_date_str.split('-'))
    end_date = Week(year, week).monday()
    
    # Generate all weeks between the start and end dates
    data = []
    current_date = start_date.date()
    while current_date <= end_date:
        year, week, _ = current_date.isocalendar()
        date_str = f"{year}-{week:02d}"
        iso_date = Week(year, week).monday().isoformat()
        commits = data_dict.get(date_str, 0)
        data.append({"date": iso_date, "commits": commits})
        current_date += timedelta(weeks=1)
    
    return jsonify(data)


@app.route('/commits-by-directory', methods=['GET'])
def get_commits_by_directory_data():
    file_data = aggregate_commits_by_directory()
    data = []
#    for date_str, num_commits in file_data:
#        year, week = map(int, date_str.split('-'))
#        iso_date = Week(year, week).monday().isoformat()
#        data.append({"date": iso_date, "commits": num_commits})
    return jsonify(data)

@app.route('/tags-frequency')
def get_tags_frequency():
    show_all = request.args.get('include_all', default=None, type=str)
    since = request.args.get('startAt', default=None, type=str)

    db_name = _get_db_name(request.args.to_dict())
    conn = sqlite3.connect(db_name)

    query = '''
        SELECT t.name, SUM(ct.value) AS total_value
        FROM tags t
        JOIN commit_tags ct ON t.id = ct.tag_id
        GROUP BY t.name
        ORDER BY total_value DESC
    '''

    if since is not None:
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query = f'''
            SELECT t.name, SUM(ct.value) AS total_value
            FROM tags t
            JOIN commit_tags ct ON t.id = ct.tag_id
            JOIN commits c ON ct.commit_id = c.id
            WHERE c.timestamp >= {since_ts}
            GROUP BY t.name
            ORDER BY total_value DESC
        '''

    tags_data = conn.execute(query).fetchall()
    conn.close()
    tags_frequency = []
    for row in tags_data:
        rounded_value = round(row[1], 2)
        formatted_value = f"{rounded_value:.2f}"
        tags_frequency.append({"name": row[0], "total_value": formatted_value})

    if show_all is not None:
        if show_all == 'false':
            if len(tags_frequency) > 11:
                the_rest = {"name": "Other", "total_value": sum([float(tag['total_value']) for tag in tags_frequency[11:]])}
                tags_frequency = tags_frequency[:11]
                rounded_value = round(the_rest['total_value'], 2)
                formatted_value = f"{rounded_value:.2f}"
                the_rest['total_value'] = formatted_value
                tags_frequency.append(the_rest)
        
    return jsonify(tags_frequency)


@app.route('/commits-by-tag-week')
def get_commits_by_tag_week():
    since = request.args.get('startAt', default=None, type=str)

    db_name = _get_db_name(request.args.to_dict())
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    if since is not None:
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query = f'''
            SELECT t.name, ct.value, c.timestamp
            FROM tags t
            JOIN commit_tags ct ON t.id = ct.tag_id
            JOIN commits c ON ct.commit_id = c.id
            WHERE c.timestamp >= {since_ts}
        '''
    else:
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
    if since:
        since_date = datetime.strptime(since, '%m/%d/%Y')
    else:
        since_date = min(datetime.fromtimestamp(row[2]) for row in rows)
    current_date = datetime.now()
    week_list = []
    while since_date <= current_date:
        year, week, _ = since_date.isocalendar()
        week_list.append(f"{year}-{week:02d}")
        since_date += timedelta(weeks=1)

    result = []
    for week in week_list:
        result.append({
            "week": week,
            "tags": data[week]
        })

    for week in result:
        for tag in week['tags']:
            week['tags'][tag] = round(week['tags'][tag], 2)

    return jsonify(result)


@app.route('/pull-requests-over-time')
def pull_requests_over_time():
    db_name = _get_db_name(request.args.to_dict())
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    since = request.args.get('startAt', default=None, type=str)
    since_clause = ''
    if since is not None:
        since_s = datetime.strptime(since, '%m/%d/%Y')
        since_clause = f' WHERE closed_at >= \'{since_s}\''

    query = f'''
        SELECT strftime('%Y-%m-%d', merged_at) as date, COUNT(*) as pr_count,
        title, html_url, number, user_login
        FROM pull_requests
        {since_clause}
        GROUP BY number
        ORDER BY date
    '''

    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    
    data = defaultdict(lambda: defaultdict(int))
    for closed_date, commit_count, title, html_url, pr_number, user_login in result:
        closed_datetime = datetime.strptime(closed_date, '%Y-%m-%d')
        year, week, _ = closed_datetime.isocalendar()
        week_str = f"{year}-{week:02d}"
        data[pr_number]['week_str'] = week_str
        data[pr_number]['pr_count'] += commit_count
        data[pr_number]['pr_title'] = title
        data[pr_number]['pr_url'] = html_url
        data[pr_number]['user'] = user_login
        data[pr_number]['date'] = closed_datetime.strftime('%Y-%m-%d')

    chart_data = [{ 'pr_number': pid, 
                    'file_count': data[pid]['pr_count'],
                    'pr_title': data[pid]['pr_title'],
                    'pr_url': data[pid]['pr_url'],
                    'date': data[pid]['date'],
                    'week_str': data[pid]['week_str'],
                    'user': data[pid]['user'],
                   } for pid in data.keys()]
    return jsonify(chart_data)


@app.route('/file-churn-icicle')
def generate_icicle_json():
    db_name = _get_db_name(request.args.to_dict())
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # here we ignore files that have null descriptions
    # because (earlier) we don't generate descriptions
    # for files that are not code files as spec'd in the config
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
        color = COLORS[depth % len(COLORS)]
        for key, value in d.items():
            if isinstance(value, dict):
                result.append({
                    "name": key,
                    "color": color,
                    "children": build_hierarchy(value, depth + 1)
                })
            else:
                result.append({
                    "name": key,
                    "color": color,
                    "size": value
                })
        return result
    # Build the final JSON structure
    json_data = {
        "name": "repo",
        "children": build_hierarchy(data)
    }

    return jsonify(json_data)

@app.route('/explain', methods=['POST'])
def summarize_data_with_ai():
    try:
        data = request.json
        print(f"Received data: {data}")
        # You can process the data here and return a response
        return jsonify({"status": "success", "message": "Data received", "data": data}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": "Failed to process data"}), 400


# Query 1
def query_contributions_by_author(request_dict, since=None):
    db_name = _get_db_name(request_dict)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()    
    
    query = """
    SELECT author, COUNT(DISTINCT commit_hash) as total_commits
    FROM commits
    """
#    since = '1704729920'
    # Adding date filter if 'since' is provided
    if since:        
        # since exists as mm/dd/yyyy
        # convert to timestamp
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query += f" WHERE timestamp >= '{since_ts}'"
    
    query += " GROUP BY author"
    query += " ORDER BY total_commits DESC LIMIT 25" 

    print(query)

    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result

# Query 2: Changes by File
def get_changes_by_file(request_dict, since=None):
    db_name = _get_db_name(request_dict)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()    

    
    # Base query to get unique commits count per file
    query = """
    SELECT filename, COUNT(DISTINCT commit_hash) as total_unique_commits
    FROM commits 
    """
    
    # Adding date filter if 'since' is provided
    if since:        
        # since exists as mm/dd/yyyy
        # convert to timestamp
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query += f" WHERE timestamp >= '{since_ts}'"
    
    query += " GROUP BY filename"
    query += " ORDER BY total_unique_commits DESC LIMIT 25"  
    
    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result


# Query 3: Contributions Over Time
def get_contributions_over_time_by_week(request_dict, since=None):
    db_name = _get_db_name(request_dict)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()    
    
    # Base query to get unique commits count per week (Sunday to Saturday)
    query = """
    SELECT 
        strftime('%Y-%W', date) as week,
        COUNT(DISTINCT commit_hash) as total_unique_commits
    FROM commits
    """

    # Adding date filter if 'startAt' is provided
    if since:
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query += f" WHERE timestamp >= '{since_ts}'"
    
    query += " GROUP BY week ORDER BY week"


    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result


# Query 4: Aggregate Commits by Directory
def aggregate_commits_by_directory(since=None, num_levels=None):
    request_args = request.args.to_dict()
    file_list = get_changes_by_file(request_args, since=since)
    dir_commits = {}
    dir_count = 0
    
    # Regular expression to match the pattern {old => new}
    pattern = r'\{([^}]+)\s=>\s([^}]*)\}'

    for file, commit_count in file_list:
        # Check if the file name contains the pattern and extract the new path
        match = re.search(pattern, file)
        if match:
            file = re.sub(pattern, match.group(1), file)

        full_path = os.path.dirname(file)
        if num_levels is not None:
            path_parts = full_path.split(os.sep)
            directory = os.sep.join(path_parts[:num_levels])
        else:
            directory = full_path
        
        if directory not in dir_commits:
            dir_commits[directory] = 0
            dir_count += 1
        dir_commits[directory] += commit_count
    
    for directory, commit_count in dir_commits.items():
        print(f"{directory} - {commit_count} commits")
    
    return dir_commits, dir_count

def _get_first_commit_date(request_dict):
    if not os.path.exists(_get_db_name(request_dict)):
        return None
    
    conn = sqlite3.connect(_get_db_name(request_dict))
    cursor = conn.cursor()    
    
    query = """
    SELECT 
        date FROM commits
        ORDER BY date ASC LIMIT 1
    """

    # Execute the query
    cursor.execute(query)
    result = cursor.fetchone()
    date_obj = datetime.strptime(result[0], '%Y-%m-%dT%H:%M:%S')
    # Format the datetime object to the desired format
    formatted_date = date_obj.strftime('%m/%d/%Y')
    conn.close()
    return formatted_date

def _get_last_run(repo_parent, repo_name):
    f = open(f'../output/master_log.txt', 'r')
    lines = f.readlines()
    f.close()
    last_ran = ""
    for line in lines:        
        parts = line.split('\t')
        if len(parts) == 4:
            parent = parts[0].strip()
            named = parts[1].strip()
            which = parts[2].strip()
            iso_date = parts[3].strip()
            if parent == repo_parent and named == repo_name and which == 'last_completed':
                last_ran = datetime.fromisoformat(iso_date)
                last_ran = last_ran.strftime('%m/%d/%Y')
    return last_ran





def _get_db_name(request_dict):
    repo_parent = request_dict.get('repo_parent')
    repo_name = request_dict.get('repo_name')
    return f"../output/{repo_parent}-{repo_name}.db"

if __name__ == '__main__':
    app.run(debug=True)