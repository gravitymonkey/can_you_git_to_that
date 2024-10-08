import logging
import os
import sqlite3
import datetime 
from .export_git import get_commit_log, get_pr_data, create_csv
from .import_to_db import fill_db
from .annotate_commits import generate_descriptions, generate_pr_descriptions, generate_tag_annotations, backfill_descriptions_from_log
from .insights import generate_insights
from .llm_config import get_base_url, get_key, init_cost_tracker
from .build_rag import init_rag, copy_code
from .code_tree import build_tree, init_tinydb

def run(config):

    # these values need to be there, or else we'll throw an error
    repo_name = config["repo_name"]
    repo_owner = config["repo_owner"]
    access_token = config["github_access_token"]
    repo_local_full_path = config["repo_local_full_path"]
    

    # these values can be blank or missing
    exclude_files = config.get("exclude_file_pattern", "")
    exclude_authors = config.get("exclude_authors", "")
    max_summary_length = int(config.get("ai_description_max", 800)) 
    ai_model = config.get("ai_description_model", "ollama|mistral")    
    summary_ai_model = config.get("ai_summary_model", "ollama|mistral")
    use_commit_desc_from_log = config.get("use_commit_desc_from_log", "False")
    start_date = config.get("start_date", _get_oldest_commit_date(repo_owner, repo_name))
    end_date = config.get("end_date", _get_newest_commit_date(repo_owner, repo_name))

    _log_master("last_started", repo_owner, repo_name, datetime.datetime.now().isoformat())

    git_log = get_commit_log(access_token, repo_owner, repo_name)
    logging.info("Log output written to %s", git_log)

    pr_log = get_pr_data(access_token, repo_owner, repo_name)
    logging.info("PR output written to %s", pr_log)

    commit_csv = create_csv(repo_owner, 
                            repo_name, 
                            git_log, 
                            exclude_file_pattern=exclude_files, 
                            exclude_author_pattern=exclude_authors)
    logging.info("Commit csv written to %s", commit_csv)

    db_path = fill_db(config)
    logging.info("Database written to %s", db_path)

    logging.info("Check backfill descriptions from log")
    backfill_descriptions_from_log(repo_owner, repo_name, use_commit_desc_from_log)    

    logging.info("Init cost tracker")
    cost_to_date = init_cost_tracker(repo_owner, repo_name)
    logging.info("Historical LLM API cost for %s to date: $%s", repo_name, cost_to_date)
    # add logic here to close if we're over a certain amount of total cost

    logging.info("Generating commit diff descriptions")
    generate_descriptions(access_token, repo_owner, repo_name, max_summary_length, ai_model)

    logging.info("Generating pull request descriptions from commit descriptions")
    generate_pr_descriptions(repo_owner, repo_name, max_summary_length, summary_ai_model)    

    logging.info("Generating annotations/tagging commits")
    generate_tag_annotations(repo_owner, repo_name, ai_model)

    logging.info("Copying code to output source directory for analysis")
    copy_code(repo_local_full_path, repo_owner, repo_name)

    logging.info("Building code syntax tree")
    build_tree(repo_local_full_path, repo_owner, repo_name, ai_model)
    logging.info("Building in-memory TinyDB of code-tree")
    init_tinydb(repo_owner, repo_name)

    logging.info("Init Retrieval Augmented Generation (RAG) for Chat")
    init_rag(True, repo_local_full_path, repo_owner, repo_name)

    logging.info("Generate LLM summary core data")
    if start_date is None:
        start_date = _get_oldest_commit_date(repo_owner, repo_name)
    if end_date is None:
        end_date = _get_newest_commit_date(repo_owner, repo_name)
    generate_insights(repo_owner, repo_name, summary_ai_model, start_date, end_date)



    _log_master("last_completed", repo_owner, repo_name, datetime.datetime.now().isoformat())

def _log_master(key, repo_owner, repo_name, value):
    with open("output/master_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{repo_owner}\t{repo_name}\t{key}\t{value}\n")

def setup_logging(level=logging.INFO):
    """
    Set up the logging configuration.
    """
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')    

def _get_oldest_commit_date(repo_owner, repo_name):
    try:
        conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
        cursor = conn.cursor()
        cursor.execute('SELECT MIN(date) FROM commits')
        oldest_date = cursor.fetchone()[0]
        conn.close()
        return oldest_date
    except Exception as e:
        logging.error("Error getting oldest commit date: %s", e)
        return None

def _get_newest_commit_date(repo_owner, repo_name):
    try:
        conn = sqlite3.connect(f"output/{repo_owner}-{repo_name}.db")
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(date) FROM commits')
        newest_date = cursor.fetchone()[0]
        conn.close()
        return newest_date
    except Exception as e:
        logging.error("Error getting newest commit date: %s", e)
        return None


def read_config(filename=None):
    """
    Read the configuration from a file.

    Args:
        filename (str, optional): The name of the configuration file. Defaults to "config.txt".

    Returns:
        dict: A dictionary containing the configuration.
    """
    logging.info("Starting to read configuration")
    config = {}
    if filename is None:
        filename = "config.txt"
        logging.info("No filename provided. Using default: %s", filename)
    else:
        logging.info("Using provided filename: %s", filename)

    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
        logging.info("Successfully read %d lines from %s", len(lines), filename)
    except FileNotFoundError:
        logging.error("Config File not found: %s", filename)
        return config

    valid_keys = [
        "repo_name",
        "repo_owner",
        "repo_local_full_path",
        "exclude_file_pattern",
        "exclude_authors",
        "tags",
        "ai_description_max",
        "ai_description_model",
        "ai_summary_model",
    ]

    for line in lines:
        data = line.strip()
        if data == "" or data.startswith("#"):
            continue
        
        data = data.split("\t")
        if len(data) < 2:
            logging.error("Invalid line in config file: %s", line)
            continue
        
        key = data[0].lower()
        val = data[1].strip()
        if key in valid_keys:
            config[key] = val

    if 'tags' in config:
        config['tags'] = [tag.strip() for tag in config['tags'].split(',')]        

    try:
        _read_github_key(config)
    except ValueError as e:
        logging.error("Error reading GitHub access token from environment variable")
        logging.error(e)

    logging.info("Finished reading configuration")
    return config

def _read_github_key(config):
    """
    Read the GitHub access token from environment variables    
    """
    config["github_access_token"] = os.environ.get("CYGTT_GITHUB_ACCESS_TOKEN")
    if config["github_access_token"] is None:
        logging.error("GitHub access token not found in environment variables")
        logging.error("SET an environment variable CYGTT_GITHUB_ACCESS_TOKEN with your GitHub access token")   
        raise ValueError("No GitHub access token found - Check docs for more information")

