import os
import pandas as pd
import sqlite3
import logging

def _connect_to_db(db_name):
    return sqlite3.connect(db_name)

def _insert_data(config, conn):
    repo_name = config['repo_name']
    repo_owner = config['repo_owner']
    
    cursor = conn.cursor()

    # Load CSV files into DataFrames
    commits_df = pd.read_csv(f'output/{repo_owner}-{repo_name}.csv')
    # Create commits tables, if it doesn't exist
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS commits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commit_hash TEXT,
                timestamp INTEGER,
                date TEXT,
                author TEXT,
                email TEXT,
                filename TEXT,
                churn_count INTEGER,
                description TEXT,
                UNIQUE(commit_hash, filename)
            )
        ''')

    # Insert data into the commits table while respecting the unique constraint
    count_dupes = 0
    for index, row in commits_df.iterrows():
        try:
            cursor.execute('''
                    INSERT INTO commits (commit_hash, timestamp, date, author, email, filename, churn_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['commit_hash'], row['timestamp'], row['date'], row['author'], row['email'], row['filename'], row['churn_count']))
        except sqlite3.IntegrityError:
            # Skip the duplicate entry
            logging.debug("Commit already exists for commit_hash: %s and filename: %s.", row['commit_hash'], row['filename'])
            count_dupes += 1

    conn.commit()
    if count_dupes > 0:
        logging.info("Skipped %d duplicate entries.", count_dupes)

    # create tags table, if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE            
        )
    ''')

    tags = config.get('tags', [])

    for tag in tags:
        cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag,))

    # Create commit_tags table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commit_tags (
            commit_id INTEGER,
            tag_id INTEGER,
            value REAL,
            PRIMARY KEY (commit_id, tag_id),
            FOREIGN KEY (commit_id) REFERENCES commits(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
    ''')

    conn.commit()

def _import_pull_requests(config, conn):
    repo_name = config['repo_name']
    repo_owner = config['repo_owner']
    file_path = f'output/{repo_owner}-{repo_name}_pull_requests.txt'
    pull_requests_df = pd.read_csv(file_path, delimiter='\t')

    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pull_requests (
            id INTEGER PRIMARY KEY,
            number INTEGER,
            title TEXT,
            user_login TEXT,       
            state TEXT,
            created_at TEXT,
            merged INTEGER,
            merged_at TEXT,
            merge_commit_sha TEXT,
            mergeable TEXT,
            mergeable_state TEXT,
            comments TEXT,
            review_comments TEXT,
            closed_at TEXT,
            html_url TEXT, 
            description TEXT
        )
    ''')

    pull_requests_df.to_sql('pull_requests', conn, if_exists='append', index=False)

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pull_requests_merge_commit_sha ON pull_requests (merge_commit_sha)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pull_requests_merged_at ON pull_requests (merged_at)')

    conn.commit()

def _create_summaries_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            hash TEXT,
            summary TEXT,
            ai_service TEXT,
            ai_model TEXT,
            start_date DATE,
            end_date DATE,
            createdAt DATE,
            UNIQUE(name, hash)
        )
    ''')
    conn.commit()


def fill_db(config, drop_existing=False):
    """
    Create (if needed) and fill the database with data from exported data.
    
    Args:
        repo_name (str): The name of the repository.
        drop_existing (bool, optional): Whether to drop the existing database before filling it. Defaults to False.
    """
    repo_name = config['repo_name']
    repo_owner = config['repo_owner']
    db_path = f'output/{repo_owner}-{repo_name}.db'
    if drop_existing and os.path.exists(db_path):
        os.remove(db_path)
        
    conn = _connect_to_db(db_path)
    _insert_data(config, conn)
    _import_pull_requests(config, conn)
    _create_summaries_table(conn)  # Ensure the summaries table is created
    conn.close()

    return db_path