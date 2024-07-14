
from can_you_git_to_that import read_config, run

config = read_config()
run(config)

#f = open("keys.txt", "r")
#lines = f.readlines()
#for line in lines:
#    data = line.strip().split(":") 
#    print(data)
#    if data[0] == "GITHUB_ACCESS_TOKEN":
#        access_token = data[1].strip()
#f.close()


#git_log = save_git_log(repo_name, full_path, access_token, repo_owner)
#get_pr_data = get_pr_data(access_token, repo_owner, repo_name)
#git_log = "output/diem-backend_git_log.txt"
#git_log_to_csv.create_csv(
#        repo_name, git_log,"\.gem|\.lock|yarn|gemfile", "dependabot|github"
#    )
#do_analysis(repo_name, f"output/{repo_name}.csv", full_path)

# don't do this after we've filled it! esp. with descriptions
#fill_db(repo_name, True)
#set_db_name(f'output/{repo_name}.db')
#run_queries(full_path, repo_name)

