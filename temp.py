import random
from datetime import datetime, timedelta

# Function to generate synthetic data
def generate_synthetic_data(start_date, end_date, num_points):
    current_date = start_date
    data = []

    while current_date <= end_date:
        value = random.randint(1, 10)  # Random value between 1 and 10
        data.append((current_date.strftime('%Y-%m-%d'), value))
        current_date += timedelta(days=random.randint(1, 10))  # Random interval between 1 and 10 days

    return data

# Define the start and end dates for the 3 months period
start_date = datetime.strptime('2022-03-01', '%Y-%m-%d')
end_date = datetime.strptime('2024-09-30', '%Y-%m-%d')

# Generate synthetic data
synthetic_data = generate_synthetic_data(start_date, end_date, num_points=30)

# Print the generated data
s = "["
for entry in synthetic_data:
    s += str(entry) 
    s += ", "

s += "]"

print(s)

