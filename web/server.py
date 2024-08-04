# app.py
import sqlite3
import math
import glob
import os
import re
from collections import namedtuple, defaultdict
from datetime import datetime, timedelta, date as ddate
from isoweek import Week
import pprint as pp
import traceback
import time
from flask_socketio import SocketIO, send

from flask import Flask, request, jsonify, send_from_directory, render_template

app = Flask(__name__, static_url_path='', static_folder='static')
socketio = SocketIO(app)

COLORS = [ '#D98943', '#D9A78B', '#59696D', '#8CD0B6','#465659', '#7CA2A6', '#172626']

# the root page, which shows a list of repos, if available
@app.route('/')
def serve_index():
    repos = []
    for db_file in glob.glob('../output/*.db'):
        repo_name = os.path.basename(db_file).replace('.db', '')
        repo_name = repo_name.replace('-', '/', 1)
        repos.append(repo_name)
    return render_template('index.html', repos=repos)


# the default page of data for a given repo
@app.route('/<repo_parent>/<repo_name>')
def serve_repo(repo_parent, repo_name):
    if repo_parent == 'static':
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
    
    return render_template('default.html',    
                            repo_parent=repo_parent, 
                            repo_name=repo_name,
                            startAt=startAt,
                            endAt=endAt)

@app.route('/<repo_owner>/<repo_name>/query', methods=['GET', 'POST'])
def query(repo_owner, repo_name):
    return render_template('query.html', repo_parent=repo_owner, repo_name=repo_name)

@socketio.on('message')
def handle_message(data):
    print('Received message:', data['message'])
    time.sleep(5)
    response = 'This is a response from the server. ' + data['message']
    send({'message': response}, broadcast=True)

# 1: Commits By Author
@app.route('/author-commits', methods=['GET'])
def get_author_commits():
    request_args = request.args.to_dict()
    since = request_args.get('startAt', None)

    db_name = _get_db_name(request_args)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()    
    
    # 1: Commits By Author
    query = """
    SELECT author, COUNT(DISTINCT commit_hash) as total_commits
    FROM commits
    """
    # Adding date filter if 'since' is provided
    if since:        
        # since exists as mm/dd/yyyy
        # convert to timestamp
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query += f" WHERE timestamp >= '{since_ts}'"
    
    query += " GROUP BY author"
    query += " ORDER BY total_commits DESC LIMIT 50" 


    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()

    author_data = result

    data = []
    for author, num_commits in author_data:
        data.append({"author": author, "commits": num_commits})
    return jsonify(data)

# 2: Commits By Filename
@app.route('/file-changes', methods=['GET'])
def get_file_changes_data():
    request_args = request.args.to_dict()
    since = request_args.get('startAt', None)

    db_name = _get_db_name(request_args)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()    

    # 2: Commits By Filename
    # Base query to get unique commits count per file
    query = """
    SELECT filename, COUNT(DISTINCT commit_hash) as total_unique_commits
    FROM commits 
    WHERE description is not NULL 
    """
    
    # Adding date filter if 'since' is provided
    if since:        
        # since exists as mm/dd/yyyy
        # convert to timestamp
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query += f" AND timestamp >= '{since_ts}'"
    
    query += " GROUP BY filename"
    query += " ORDER BY total_unique_commits DESC LIMIT 50"  

    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()

    data = []
    for author, num_commits in result:
        data.append({"filename": author, "commits": num_commits})
    return jsonify(data)

# 3 Commits Over Time
@app.route('/commits-over-time', methods=['GET'])
def get_commits_over_time_data():
    request_args = request.args.to_dict()
    since = request_args.get('startAt', None)

    db_name = _get_db_name(request_args)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()    
    

    # Base query to get unique commits count per day
    query = """
    SELECT 
        strftime('%Y-%m-%d', date) as day,
        COUNT(DISTINCT commit_hash) as total_unique_commits,
        COUNT(DISTINCT filename) as unique_filenames_per_day
    FROM commits
    """

    # Adding date filter if 'startAt' is provided
    if since:
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query += f" WHERE timestamp >= '{since_ts}'"
    
    query += f" GROUP BY day ORDER BY day"

    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()

    # 3 Commits Over Time
    data_dict = {}
    for row in result:
        tstring = datetime.strptime(str(row[0]), '%Y-%m-%d')
        data_dict[tstring] = {"commit": row[1], "files": row[2]}
    
    # Determine the date range
    if since:
        start_date = datetime.strptime(since, '%m/%d/%Y')        
    else:
        start_date = min(data_dict.keys())
    
    # how many days from first date to now?

    # Parse the last date string in the data_dict keys
    end_date = max(data_dict.keys())
    date_difference = end_date - start_date
    resolution = "Day"
    if date_difference.days > 90:
        resolution = "Week"
    
    # Initialize the date range and counts
    date_counts = defaultdict(int)
    file_counts = defaultdict(int)


    # Generate date range based on resolution
    if resolution == "Day":
        current_date = start_date
        while current_date <= end_date:
            dd = data_dict.get(current_date, {})
            date_counts[current_date] = dd.get('commit', 0)
            file_counts[current_date] = dd.get('files', 0)            
            current_date += timedelta(days=1)
    elif resolution == "Week":
        current_date = start_date - timedelta(days=start_date.weekday())  # Start from the beginning of the week
        while current_date <= end_date:
            date_counts[current_date] = sum(data_dict.get(current_date + timedelta(days=i), 0) for i in range(7))
            file_counts = sum(data_dict.get(current_date + timedelta(days=i), 0) for i in range(7))
            current_date += timedelta(weeks=1)
    else:
        raise ValueError("Invalid resolution. Choose from 'Day' or 'Week'")

    # Convert the date_counts to a sorted list of tuples (date, count)
    result = sorted(date_counts.items())

    # Print result
    data_overall = {"type": resolution}
    data = []
    for date, count in result:
        filec = file_counts[date]
        data.append({"date": date.strftime('%Y-%m-%d'), "commits": count, "files": filec})
    data_overall['data'] = data
    return jsonify(data_overall)

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


@app.route('/pull-requests-recent')
def pull_requests_recent():
    db_name = _get_db_name(request.args.to_dict())
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    since = request.args.get('startAt', default=None, type=str)
    since_clause = ''
    if since is not None:
        since_s = datetime.strptime(since, '%m/%d/%Y')
        since_clause = f' WHERE pr.closed_at >= \'{since_s}\''

    query = f'''
        SELECT 
            strftime('%Y-%m-%d', pr.merged_at) AS date, 
        COUNT(c.filename) AS file_count,
            pr.title, 
            pr.html_url, 
            pr.number, 
            pr.user_login,
            pr.description
        FROM 
            pull_requests pr
        JOIN 
            commits c 
        ON 
            pr.merge_commit_sha = c.commit_hash
        {since_clause}
        GROUP BY 
            pr.number
        ORDER BY 
            date DESC
        LIMIT
            10;           
    '''

    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    
    data = defaultdict(lambda: defaultdict(int))
    for closed_date, commit_count, title, html_url, pr_number, user_login, description in result:
        closed_datetime = datetime.strptime(closed_date, '%Y-%m-%d')
        year, week, _ = closed_datetime.isocalendar()
        week_str = f"{year}-{week:02d}"
        data[pr_number]['week_str'] = week_str
        data[pr_number]['pr_count'] += commit_count
        data[pr_number]['pr_title'] = title
        data[pr_number]['pr_url'] = html_url
        data[pr_number]['user'] = user_login
        data[pr_number]['date'] = closed_datetime.strftime('%Y-%m-%d')
        description = description.replace("\n", "<BR>")
        for x in range(1,10):
            description = description.replace(f"{x}. ", "&nbsp;&#8226;&nbsp;")
        data[pr_number]['description'] = description

    chart_data = [{ 'pr_number': pid, 
                    'file_count': data[pid]['pr_count'],
                    'pr_title': data[pid]['pr_title'],
                    'pr_url': data[pid]['pr_url'],
                    'date': data[pid]['date'],
                    'week_str': data[pid]['week_str'],
                    'user': data[pid]['user'],
                    'description': data[pid]['description']
                   } for pid in data.keys()]
    return jsonify(chart_data)


@app.route('/file-churn')
def generate_sunburst_json():
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
        request_type = data['request_type']
        data = _get_summary(_get_db_name(data), request_type)
        if not data is None:
            return jsonify({"status": "success", 
                            "message": "Data received", 
                            "summary": data['summary'],
                            "service": data['ai_service'],
                            "model": data['ai_model'],
                            "startAt" : data['start_date'],
                            "endAt" : data['end_date'],
                            }), 200
        else:
            return jsonify({"status": "empty", "message": "No Data", "summary": "- -"}), 200

    except Exception as e:
        traceback.print_exc() 
        return jsonify({"status": "error", "message": "Failed to process data"}), 400

def _process_date(datetime_str):
    dx = datetime_str.split("T")[0]
    dx = dx.replace("-", "/")
    return dx

def _get_summary(db_name, request_type):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # here we ignore files that have null descriptions
    # because (earlier) we don't generate descriptions
    # for files that are not code files as spec'd in the config
    cursor.execute("""
        SELECT * from summaries where name = ?
        ORDER BY createdAt DESC LIMIT 1
    """, (request_type,))
    data = cursor.fetchone()
    conn.close()
    result = {}
    if data is not None:
        result['id'] = data[0]
        result['name'] = data[1]
        result['hash'] = data[2]
        result['summary'] = data[3]
        result['ai_service'] = data[4]
        result['ai_model'] = data[5]
        result['start_date'] = _process_date(data[6])
        result['end_date'] = _process_date(data[7])
        result['createdAt'] = data[8]

    return result



# Query 4: Aggregate Commits by Directory
#def aggregate_commits_by_directory(since=None, num_levels=None):
#    request_args = request.args.to_dict()
#    file_list = get_changes_by_file(request_args, since=since)
#    dir_commits = {}
#    dir_count = 0
    
    # Regular expression to match the pattern {old => new}
#    pattern = r'\{([^}]+)\s=>\s([^}]*)\}'

#    for file, commit_count in file_list:
        # Check if the file name contains the pattern and extract the new path
#        match = re.search(pattern, file)
#        if match:
#            file = re.sub(pattern, match.group(1), file)

#        full_path = os.path.dirname(file)
#        if num_levels is not None:
#            path_parts = full_path.split(os.sep)
#            directory = os.sep.join(path_parts[:num_levels])
#        else:
#            directory = full_path
        
#        if directory not in dir_commits:
#            dir_commits[directory] = 0
#            dir_count += 1
#        dir_commits[directory] += commit_count
        
#    return dir_commits, dir_count

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
#    app.run(debug=True)
    socketio.run(app, debug=True)    