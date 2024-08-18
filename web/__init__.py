server_config = {}

f = open('./web/config.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()

for line in lines:
    line = line.strip()
    if not line.startswith("#"):
        parts = line.split('\t')
        if len(parts) == 2:
            key = parts[0].strip()
            value = parts[1].strip()
            server_config[key] = value
