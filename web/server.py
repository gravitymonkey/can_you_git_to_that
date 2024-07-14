# app.py
import sqlite3
import math
import glob
import os
import re
from collections import namedtuple, defaultdict
from datetime import datetime, timedelta
from isoweek import Week


from flask import Flask, request, jsonify, send_from_directory, render_template

app = Flask(__name__, static_url_path='', static_folder='static')

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'default.html')

@app.route('/<repo_parent>/<repo_name>')
def serve_repo(repo_parent, repo_name):
    # Capture query string parameters
    query_params = request.args.to_dict()
    if 'startAt' in query_params:
        startAt = query_params['startAt'] 
        return render_template('index.html',    
                            repo_parent=repo_parent, 
                            repo_name=repo_name, 
                            startAt=startAt)
    else:
     return render_template('index.html',    
                            repo_parent=repo_parent, 
                            repo_name=repo_name)

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
    data = []
    for date_str, num_commits in file_data:
        year, week = map(int, date_str.split('-'))
        iso_date = Week(year, week).monday().isoformat()
        data.append({"date": iso_date, "commits": num_commits})
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

    conn = sqlite3.connect("../../output/diem-backend.db")
    cursor = conn.cursor()    

    query = '''
        SELECT t.name, COUNT(ct.commit_id) AS commit_count
        FROM tags t
        JOIN commit_tags ct ON t.id = ct.tag_id
        GROUP BY t.name
        ORDER BY commit_count DESC 
    '''

    if since is not None:
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query = f'''
            SELECT t.name, COUNT(ct.commit_id) AS commit_count
            FROM tags t
            JOIN commit_tags ct ON t.id = ct.tag_id
            JOIN commits c ON ct.commit_id = c.id
            WHERE c.timestamp >= {since_ts}
            GROUP BY t.name
            ORDER BY commit_count DESC 
        '''

    tags_data = conn.execute(query).fetchall()
    conn.close()
    tags_frequency = []
    for row in tags_data:
        tags_frequency.append({"name": row[0], "commit_count": row[1]})

    if show_all is not None:
        if show_all == 'false':
            if len(tags_frequency) > 11:
                the_rest = {"name": "Other", "commit_count": sum([tag['commit_count'] for tag in tags_frequency[11:]])}
                tags_frequency = tags_frequency[:11]
                tags_frequency.append(the_rest)
        
    return jsonify(tags_frequency)


@app.route('/commits-by-tag-week', methods=['GET'])
def get_commits_by_tag_week():
    conn = sqlite3.connect("../../output/diem-backend.db")
    cursor = conn.cursor()
    since = request.args.get('startAt', default=None, type=str)

    # Query to get commits with their tags and timestamps
    query = '''
    SELECT t.name, c.timestamp
    FROM tags t
    JOIN commit_tags ct ON t.id = ct.tag_id
    JOIN commits c ON ct.commit_id = c.id
    '''

    if since is not None:
        since_ts = datetime.strptime(since, '%m/%d/%Y').timestamp()
        query = query + f' WHERE c.timestamp >= {since_ts}'


    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()


    data = defaultdict(lambda: defaultdict(int))

    for tag, commit_date in rows:
        commit_datetime = datetime.strptime(commit_date, '%Y-%m-%dT%H:%M:%S')
        year, week, _ = commit_datetime.isocalendar()
        week_str = f"{year}-{week:02d}"
        data[week_str][tag] += 1

    # Prepare the data for the stacked bar chart
    chart_data = [{"week": week, "tags": dict(tags)} for week, tags in data.items()]

    return jsonify(chart_data)


@app.route('/pull-requests-over-time')
def pull_requests_over_time():
    conn = sqlite3.connect("../../output/diem-backend.db")
    cursor = conn.cursor()
    since = request.args.get('startAt', default=None, type=str)
    since_clause = ''
    if since is not None:
        since_s = datetime.strptime(since, '%m/%d/%Y')
        since_clause = f' WHERE closed_at >= \'{since_s}\''

    query = f'''
        SELECT strftime('%Y-%m-%d', created_at) as date, COUNT(*) as pr_count
        FROM pull_requests
        {since_clause}
        GROUP BY date
        ORDER BY date
    '''

    print(query)

    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    
    data = defaultdict(lambda: defaultdict(int))
    for closed_date, pr in result:
        closed_datetime = datetime.strptime(closed_date, '%Y-%m-%d')
        year, week, _ = closed_datetime.isocalendar()
        week_str = f"{year}-{week:02d}"
        data[week_str]['pr_count'] += pr

    chart_data = [{'date': week, 'pr_count': data[week]['pr_count']} for week in data.keys()]
    return jsonify(chart_data)


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

def _get_db_name(request_dict):
    repo_parent = request_dict.get('repo_parent')
    repo_name = request_dict.get('repo_name')
    return f"../output/{repo_parent}-{repo_name}.db"

if __name__ == '__main__':
    app.run(debug=True)