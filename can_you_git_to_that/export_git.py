import os
import logging
import sqlite3
from github import Github, GithubException
import re
from datetime import datetime
import time
from tqdm import tqdm



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
    try:
        # Initialize the GitHub object
        g = Github(github_access_token)

        # Get the repository
        full_repo_name = f"{repo_owner}/{repo_name}"
        logging.info("Getting repository: %s", full_repo_name)
        repo = g.get_repo(full_repo_name)

        # Fetch all commits

        # Determine the number of commits
        total_commits = repo.get_commits().totalCount
        logging.info("Total number of commits: %d", total_commits)

        # Fetch all commits and show loading status
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
        with tqdm(total=total_commits, desc="Loading Commits") as pbar:
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
                counter += 1
                pbar.update(1)


        # Write the output to the file
        with open(output_file_path, "w", encoding="utf-8") as output_file:
            output_file.write(output)

        return output_file_path
    except GithubException as ge:
        logging.error("Error getting repository: %s", ge)
        logging.error("Can't reach this repo - you may not have access to it with ")
        return None
    except Exception as e:
        logging.error("Error getting commit log: %s", e)
        return None



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

    existing_pr_numbers = _get_existing_pr_numbers(repo_owner, repo_name)    

    pulls = []
    prs = repo.get_pulls(state='all', sort='created', direction='asc')
    for pr in prs:
        if pr.number not in existing_pr_numbers:
            pulls.append(pr)
    num_pulls = len(pulls)

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
    with tqdm(total=num_pulls, desc="Loading Pull Requests") as pbar:
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
            pbar.update(1)

    filename = f"./output/{repo_owner}-{repo_name}_pull_requests.txt"
    with open(filename, "w", encoding="utf-8") as output_file:
        output_file.write(output)
    return filename

def _get_existing_pr_numbers(repo_owner, repo_path):
    try:
        conn = sqlite3.connect(f"output/{repo_owner}-{repo_path}.db")    
        cursor = conn.cursor()
        cursor.execute("SELECT number FROM pull_requests")
        result = cursor.fetchall()
        conn.close()
        return [x[0] for x in result]
    except Exception as e:
        logging.error("Error getting existing PR numbers: %s", e)
        return []

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
