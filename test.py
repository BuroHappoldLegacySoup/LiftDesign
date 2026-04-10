import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from gui.project_json import load_project_json


def json_to_dict(file_path):
    return load_project_json(file_path)


# Example usage
file_path = r"C:\Users\vmylavarapu\LiftDesigner\Projects\241023_LiftDesigner_3.json"
python_dict = json_to_dict(file_path)

print(python_dict)
