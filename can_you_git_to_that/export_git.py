import os
import logging
import sqlite3
from github import Github 
import re
from datetime import datetime



def get_commit_log(github_access_token, repo_owner, repo_name):
    """
    Get the commit log for a given repository.

    Args:
        github_access_token (str): The access token for the GitHub API.
        repo_owner (str): The owner of the repository.
        repo_name (str): The name of the repository.

    Returns:
        str: The file path of the output file.
    """
    # Initialize the GitHub object
    g = Github(github_access_token)

    # Get the repository
    repo = g.get_repo(f"{repo_owner}/{repo_name}")

    # Fetch all commits
    commits = repo.get_commits()

    # Get the directory of the current script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    parent_directory = os.path.dirname(script_directory)

    # Define the output folder relative to the execution location
    output_folder = os.path.join(parent_directory, 'output')
    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Define the output file path
    output_file_path = os.path.join(output_folder, f"{repo_owner}-{repo_name}_git_log.txt")

    output = ""
    counter = 0
    logging.info("Processing commits")
    for commit in commits:
        commit_data = commit.commit
        commit_message = commit_data.message
        commit_message = commit_message.replace("\n", " ")
        commit_message = commit_message.replace("--", " ")
        author = commit_data.author
        author_name = author.name if author else "Unknown"
        author_email = author.email if author else "Unknown"
        line = f"^^{commit.sha}--{commit_data.author.date.timestamp()}--{commit_data.author.date.isoformat()}--{author_name}--{author_email}--{commit_message}\n"
        output += line
        for file in commit.files:
            output += f"{file.additions}\t{file.deletions}\t{file.filename}\n"
        output += "\n"
        if (counter / 10 % 100) == 0 and counter > 0:
            logging.info("Processing commit: %s", counter)
        counter += 1

    # Write the output to the file
    with open(output_file_path, "w", encoding="utf-8") as output_file:
        output_file.write(output)

    return output_file_path



def get_pr_data(access_token, repo_owner, repo_name):
    """
    Get the pull request data for a given repository.

    Args:
        access_token (str): The access token for the GitHub API.
        repo_owner (str): The owner of the repository.
        repo_name (str): The name of the repository.
    """
    # Initialize the GitHub object
    g = Github(access_token)

    # Get the repository
    repo = g.get_repo(f"{repo_owner}/{repo_name}")

    # Get the highest PR number from the database
    highest_pr_number = _get_highest_pr_number(repo_owner, repo_name)

    # Fetch PRs using pagination and only include those greater than the highest number in the database
    pulls = []
    page = 0
    keep_going = True
    while keep_going:
        prs = repo.get_pulls(state='all', sort='created', direction='asc')
        if prs.totalCount == 0:
            break
        for pr in prs:
            if pr.number > highest_pr_number:
                pulls.append(pr)
            else:
                # Since PRs are sorted by creation date, if we encounter a PR number <= highest_pr_number, we can stop
                keep_going = False
                break # only breaks the inner loop, so we need to flip keep_going too
        page += 1

    # Iterate through pull requests and print details
    # column names
    column_names = [
        "number",
        "title",
        "user_login",
        "state",
        "created_at",
        "merged",
        "merged_at",
        "merge_commit_sha",
        "mergeable",
        "mergeable_state",
        "comments",
        "review_comments",
        "closed_at",
        "html_url",
        "description"
    ]
    output = "\t".join(column_names)+ "\n"
    counter = 0
    logging.info("Processing pull requests")
    for pr in pulls:
        line = ""
        line += f"{pr.number}\t"
        title = str(pr.title).replace("\t", " ")
        line += f"{title}\t"
        line += f"{pr.user.login}\t"
        line += f"{pr.state}\t"
        line += f"{pr.created_at}\t"
        line += f"{pr.merged}\t"
        line += f"{pr.merged_at}\t"
        line += f"{pr.merge_commit_sha}\t"
        line += f"{pr.mergeable}\t"
        line += f"{pr.mergeable_state}\t"
        comments = str(pr.comments).replace("\t", " ")
        line += f"{comments}\t"
        review_comments = str(pr.review_comments).replace("\t", " ")
        line += f"{review_comments}\t"
        line += f"{pr.closed_at}\t"
        line += f"{pr.html_url}\n"
        if (counter /10 % 100) == 0 and counter > 0:
            logging.info("Processing pull request: %s", counter)
        counter += 1
        output += line

    filename = f"./output/{repo_owner}-{repo_name}_pull_requests.txt"
    with open(filename, "w", encoding="utf-8") as output_file:
        output_file.write(output)
    return filename

def _get_highest_pr_number(repo_owner, repo_path):
    conn = sqlite3.connect(f"output/{repo_owner}-{repo_path}.db")    
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(number) FROM pull_requests")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result[0] is not None else 0

def create_csv(repo_parent, repo_name, log_filename, exclude_file_pattern="", exclude_author_pattern=""):
    """
    Create a CSV file from the git log.

    Args:
        repo_parent (str): The parent/owner org of the repository.
        repo_name (str): The name of the repository.
        log_filename (str): The file path of the git log.
        exclude_file_pattern (str, optional): The pattern to exclude files from the CSV. Defaults to "".
        exclude_author_pattern (str, optional): The pattern to exclude authors from the CSV. Defaults to "".
    """
    logging.info("Exclude Author Pattern: %s", exclude_author_pattern)
    logging.info("Reading git log: %s", log_filename)

    with open(log_filename, "r", encoding="utf-8") as file:
        git_log_text = file.read()

    csv_data = _process_git_log(git_log_text, exclude_file_pattern, exclude_author_pattern)

    output_filename = f"output/{repo_parent}-{repo_name}.csv"
    with open(output_filename, "w", encoding="utf-8") as file:
        file.write(csv_data)

    return output_filename


def _strip_timezone_offset(timestamp_str):
    timezone_offset_pattern = r"[+\-][0-9]{2}:[0-9]{2}$"
    return re.sub(timezone_offset_pattern, "", timestamp_str)

def _process_git_log(log, exclude_file_pattern="", exclude_author_pattern=""):
    commits = log.split("^^")
    csv_data = "commit_hash,timestamp,date,author,email,filename,churn_count\n"

    for commit in commits:
        commit = commit.strip()
        if commit:
            commit_lines = commit.split("\n")
            commit_info = commit_lines[0].split("--")

            if len(commit_info) < 5:
                logging.info("Skipping invalid commit entry: %s", commit_lines)
                continue

            commit_hash, epoch, timestamp, author, email = commit_info[:5]
            timestamp = _strip_timezone_offset(timestamp)
#            date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").date()

            if not _is_excluded(author, exclude_author_pattern):
                for churn_line in commit_lines[1:]:
                    churn_info = churn_line.split("\t")
                    if len(churn_info) < 3:
                        logging.info("Skipping invalid churn line: %s", churn_line)
                        continue

                    insertions = _parse_churn_value(churn_info[0])
                    deletions = _parse_churn_value(churn_info[1])
                    churn_count = insertions + deletions
                    file_path = churn_info[2]

                    if not _is_excluded(file_path, exclude_file_pattern):
                        csv_data += f"{commit_hash},{epoch},{timestamp},{author},{email},{file_path},{churn_count}\n"

    return csv_data

def _parse_churn_value(value):
    return int(value) if value.strip() not in ["-", ""] else 0

def _is_excluded(value, pattern):
    return bool(pattern) and bool(re.findall(pattern, value, re.IGNORECASE))