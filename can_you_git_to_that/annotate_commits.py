import sqlite3
import logging
import time
import os
import hashlib
from datetime import datetime
from github import Github
from .llm import summarize_diff, shorter_summarize_diff, classify_description

def generate_descriptions(access_token, repo_owner, repo_name, max_length, ai_model):
    conn = sqlite3.connect(f'output/{repo_owner}-{repo_name}.db')
    cursor = conn.cursor()

    rows = _get_commits(cursor)

    logging.info("loaded for %s commits", len(rows))

    for row in rows:
        id = row[0]
        sha = row[1]
        filename = row[2]
        description = row[3]
        if _is_code_file(filename):
            if description is None or description.strip() == "":
                logging.info("Generating commit diff description for %s %s %s", id, sha, filename)
                summary = _annotate_code_file(repo_owner, repo_name, sha, filename, access_token, ai_model, max_length=max_length)
                logging.info("Summary:\n%s", summary)
                success = _write_diff_summary_to_db(repo_owner, repo_name, sha, filename, summary)
                if not success:
                    logging.error("Error writing summary to DB")
                else:
                    logging.debug("Summary successfully written")

def _write_diff_summary_to_db(repo_owner, repo_name, commit_hash, filename, summary):
    conn = sqlite3.connect(f'output/{repo_owner}-{repo_name}.db')
    cursor = conn.cursor()

    # Check if the row exists
    cursor.execute('''
        SELECT COUNT(*) FROM commits WHERE commit_hash = ? AND filename = ?
    ''', (commit_hash, filename))
    row_count = cursor.fetchone()[0]

    if row_count > 0:
        # Update the existing row
        cursor.execute('''
            UPDATE commits
            SET description = ?
            WHERE commit_hash = ? AND filename = ?
        ''', (summary, commit_hash, filename))
        conn.commit()

        try:
            # Save the summary to a log file, so we can rely on that to 
            # rebuild if we need to
            f = open(f"output/{repo_owner}-{repo_name}_diffs_log.txt", "a")        
            now = time.time()  # Ensure 'now' is defined and is a valid timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
            f.write(f"{timestamp}\t{filename}\t{commit_hash}\t{summary}\n")
            f.close
        except Exception as e:
            logging.error("Error trying to write summary to log for %s, %s", filename, commit_hash)

        return True
    
    else:
        logging.error("Error trying to save summary for %s, %s not found in DB?", filename, commit_hash)

    conn.close()
    return False

def _get_file_diff_and_content(access_token, repo_owner, repo_name, commit_sha, file_name):
    try:
        unique_hash = _get_diff_hash(commit_sha, file_name)
        # Check if the diff has already been fetched and saved to disk
        if os.path.exists(f"output/cache/{unique_hash}.txt"):
            f = open(f"output/cache/{unique_hash}.txt", "r", encoding="utf-8")
            diff = f.read()
            f.close()
            logging.info("Diff found in local cache for %s %s", file_name, commit_sha)
            return diff, None
        
        g = Github(access_token)
        repo = g.get_repo(f"{repo_owner}/{repo_name}")
        logging.info("Fetching diff from Github for %s %s", file_name, commit_sha)
        commit = repo.get_commit(commit_sha)

        # Initialize variables to store the file changes and content
        file_diff = None
        file_content = None

        # Iterate through the files in the commit
        for file in commit.files:
            if file.filename == file_name:
                file_diff = file.patch
                # Fetch the file content - but only if there's no diff
                if file_diff is None:
                    blob = repo.get_git_blob(file.sha)    
                    file_content = blob.content
                break
        
        _write_diff_to_disk(commit_sha, file_name, file_diff, file_content)
        return file_diff, file_content
        
    except Exception as e:
        logging.error("Error: %s for getting diff for %s %s", e, file_name, commit_sha)

def _get_diff_hash(commit_sha, file_name):
    combined_string = f"{commit_sha}-{file_name}"    
    # Generate a SHA-256 hash of the combined string
    unique_hash = hashlib.sha256(combined_string.encode()).hexdigest()
    return unique_hash

def _write_diff_to_disk(commit_sha, file_name, file_diff, file_content):
    unique_hash = _get_diff_hash(commit_sha, file_name)
    # make sure directory exists
    os.makedirs("output/cache", exist_ok=True)
    f = open(f"output/cache/{unique_hash}.txt", "w")
    if file_diff is not None:
        f.write(file_diff)
    else:
        f.write(file_content)
    f.close()

    
    # Additional code to write the diff and content to disk can go here

def _annotate_code_file(repo_parent, repo_name, commit_sha, filename, access_token, ai_model, max_length=800):
    logging.info("Annotating commit changes for %s", filename)
    diff, file_sample = _get_file_diff_and_content(access_token, repo_parent, repo_name, commit_sha, filename)
    
    ai_info = ai_model.split("|")
    ai_service = ai_info[0]
    ai_model = ai_info[1]

    summary = summarize_diff(filename, diff, file_sample, ai_service, ai_model)
    logging.debug("summary generation\t%s\t%s:\n****\n%s\n***\n", filename, commit_sha, summary)

    if summary.strip().startswith("@@@"):
        raise ValueError("Model is spewing garbage")

    if len(summary.strip()) > max_length:
        logging.debug("Summary too long, %i (max %i), sending to shortener", len(summary), max_length)
        summary, num_tries = _attempt_to_shorten_summary(filename, summary, max_length, ai_service, ai_model)
        if summary is None:
            logging.error("Unable to shorten summary for %s %s", commit_sha, filename)    
        else:
            logging.info("Summarized in %i tries", num_tries)
    else:
        logging.info("Summarized in 1 try")

    return summary

def _attempt_to_shorten_summary(filename, summary, max_length, ai_service, ai_model):
    nu_summary = None
    counter = 1 # counting previous run in _annotate_code_file
    for attempts in range(5): #this establishes how many retries
        nu_summary = shorter_summarize_diff(filename, summary, ai_service, ai_model)
        counter += 1
        logging.debug("\tattempt %s to shorten commit on %s, currently %s:", attempts + 1, filename, len(nu_summary))
        logging.debug(nu_summary)
        if len(nu_summary.strip()) <= max_length:
            logging.debug("\tNow short enough: currently %s:", len(nu_summary))
            break
        else:
            summary = nu_summary
            nu_summary = None

    return nu_summary, counter


def _is_code_file(path):
    exclude_extensions = [
        ".md",
        ".lock",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".ico",
        ".yaml",
        ".yml",
        ".json",
        ".xml",
        ".scss",
        ".svg",
        ".ttf",
        ".ipynb",
        ".eslintcache",
        ".env.development",
        ".env.production",
        ".env.test",
        ".env.local",
        ".env.sample",
    ]
    filename, file_extension = os.path.splitext(path)
    if file_extension in exclude_extensions:
        return False
    if filename.startswith("."):
        return False
    return True


def generate_tag_annotations(repo_owner, repo_name, ai_string):
    conn = sqlite3.connect(f'output/{repo_owner}-{repo_name}.db')
    cursor = conn.cursor()

    rows = _get_commits(cursor)

    ai_service = ai_string.split("|")[0]
    ai_model = ai_string.split("|")[1]

    orig_tags = _get_tags(cursor)
    logging.info("loaded for %s commits, using %s tags", len(rows), len(orig_tags))

    counter = 0
    for row in rows:
        row_id = row[0]
        filename = row[2]
        description = row[3]
        if description is not None and description.strip() != "":
            if _is_code_file(filename):
                if not _tags_already_exist(repo_owner, repo_name, row_id):
                    tags = classify_description(orig_tags, description, ai_service, ai_model)
                    success = _write_tags_to_db(repo_owner, repo_name, row_id, orig_tags, tags)
                    if success:
                        counter += 1
    logging.info("generated %s tags on commits", counter)
    conn.close()    

def _tags_already_exist(repo_owner, repo_name, commit_id):
    conn = sqlite3.connect(f'output/{repo_owner}-{repo_name}.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM commit_tags WHERE commit_id = ?
    ''', (commit_id,))
    row_count = cursor.fetchone()[0]
    conn.close()
    if row_count > 0:
        return True
    return False

def _write_tags_to_db(repo_owner, repo_name, commit_id, orig_tags, tag_string):
    conn = sqlite3.connect(f'output/{repo_owner}-{repo_name}.db')
    cursor = conn.cursor()
    tag_string = tag_string.strip()
    tags = tag_string.split(",")
    counter = 0
    tag_values = {}
    while counter < len(tags):
        try:
            name = tags[counter].strip()
            val = int(tags[counter + 1].strip())
            if name in orig_tags:
                tag_values[name] = val
        except Exception as e:
            logging.error("Error with tagging: %s", e)
        counter += 2
    tag_values = _normalize_values_to_one(tag_values)
    status = False
    for t in tag_values:
        t = t.strip()
        v = tag_values[t]
        try:
            cursor.execute('''
                SELECT id FROM tags WHERE name = ?
            ''', (t,))
            tag_id = cursor.fetchone()[0]
            cursor.execute('''
                    INSERT INTO commit_tags (commit_id, tag_id, value)
                    VALUES (?, ?, ?)
                ''', (commit_id, tag_id, v))
            conn.commit()
            logging.debug("Saved to DB %s for tag %s for commit id %s", v, t, commit_id)
            status = True
        except Exception as e:
            logging.error("Error saving to DB %s for tag %s for commit id %s", e, t, commit_id)
    
    conn.close()
    return status

def _normalize_values_to_one(tag_dict):
    # add up all the values
    # divide each value by the sum    
    total = sum(tag_dict.values())
    for key in tag_dict:
        tag_dict[key] = tag_dict[key] / total
    return tag_dict



def _get_commits(cursor):
    query = """
    SELECT c.id, c.commit_hash, c.filename, c.description
    FROM commits c
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    return rows


def _get_tags(cursor):
    query = """
    SELECT name from tags
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    val = []
    for row in rows:
        val.append(row[0].strip())

    return val


# Function to check if a string is a valid date
def _is_valid_date(string):
    try:
        datetime.strptime(string, '%Y-%m-%d %H:%M:%S')
        return True
    except ValueError:
        return False
    
# call this if you've mistakenly dropped the DB, perhaps,
# but still have the diffs file around to avoid reprocessing
def backfill_descriptions_from_log(repo_parent, repo_name, do_backfill):

    if do_backfill is None:        
        return
    elif do_backfill.strip().lower() == "no" or do_backfill.strip().lower() == "false":
        logging.info("skip backfill commit from log - config setting is %s", do_backfill)
        return

    f = open(f"output/{repo_parent}-{repo_name}_diffs_log.txt", "r", encoding="utf-8")
    data = f.read()
    f.close()

    # Split the data into lines
    lines = data.split('\n')

    # Initialize an empty list to store the parsed records
    records = []

    # Temporary variables to hold the current record data
    current_date = None
    current_filename = None
    current_hash = None
    current_description = []

    # Parse the lines
    for line in lines:
        parts = line.split('\t', 3)
        if _is_valid_date(parts[0]):
            if current_date:
                records.append([current_date, current_filename, current_hash, "\n".join(current_description)])
            current_date = parts[0]
            current_filename = parts[1]
            current_hash = parts[2]
            current_description = [parts[3]] if len(parts) > 3 else []
        else:
            current_description.append(line)

    # Append the last record
    if current_date:
        records.append([current_date, current_filename, current_hash, "\n".join(current_description)])

    # Sort the records by filename and hash, and keep only the most recent description for each unique filename and hash combination
    sorted_records = sorted(records, key=lambda x: (x[1], x[2], datetime.strptime(x[0], '%Y-%m-%d %H:%M:%S')), reverse=True)
    unique_records = {}
    for record in sorted_records:
        key = (record[1], record[2])
        if key not in unique_records:
            unique_records[key] = record

    # Convert the unique records back to a list
    final_records = list(unique_records.values())

    # Print the final sorted and unique records
    conn = sqlite3.connect(f'output/{repo_parent}-{repo_name}.db')
    cursor = conn.cursor()

    for record in final_records:
        try:
            cursor.execute('''
                SELECT COUNT(*) FROM commits WHERE commit_hash = ? 
                AND filename = ?
                AND description IS NULL
            ''', (record[2], record[1]))
            row_count = cursor.fetchone()[0]
            if row_count == 1:
                logging.info("found one diff desc to replace by log: %s, %s", record[2], record[3])
                cursor.execute('''
                    UPDATE commits
                    SET description = ?
                    WHERE commit_hash = ? AND file = ?
                ''', (record[3], record[2], record[1]))
                conn.commit()
        except Exception as e:
            logging.error("Error updating commit %s: %s", record[2], e)
    conn.close()