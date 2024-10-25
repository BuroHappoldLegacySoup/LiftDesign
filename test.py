import json

# Function to convert JSON file to Python dictionary
def json_to_dict(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

# Example usage
file_path = r"C:\Users\vmylavarapu\LiftDesigner\Projects\241023_LiftDesigner_3.json"
python_dict = json_to_dict(file_path)

print(python_dict)
