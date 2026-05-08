"""
UTF-8 JSON I/O for project files.

Always use these helpers so Windows does not open JSON with a legacy code page
(which corrupts superscripts and other Unicode in keys, e.g. ``m/s²`` → ``m/sÃ‚Â²``).
"""
from __future__ import annotations

import json
from typing import Any

from gui.project_lift_schema import finalize_project_json_for_save, normalize_project_lift_data


def _repair_mojibake_key(s: str) -> str:
    """Fix common UTF-8 read-as-latin1 key corruption (recursive latin1→utf8 rounds)."""
    if not isinstance(s, str) or ('Ã' not in s and 'Â' not in s):
        return s
    t = s
    for _ in range(4):
        try:
            n = t.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return t
        if n == t:
            return t
        t = n
    return t


def repair_dict_keys_mojibake(obj: Any) -> Any:
    """Rewrite dict keys that were stored with mojibake; recurse into dicts and lists."""
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            nk = _repair_mojibake_key(k) if isinstance(k, str) else k
            out[nk] = repair_dict_keys_mojibake(v)
        return out
    if isinstance(obj, list):
        return [repair_dict_keys_mojibake(x) for x in obj]
    return obj


def load_project_json(path: str) -> Any:
    """Load project JSON with UTF-8 (accepts UTF-8 BOM via utf-8-sig). Repair bad key encodings."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    data = repair_dict_keys_mojibake(data)
    if isinstance(data, dict):
        normalize_project_lift_data(data)
    return data


def save_project_json(path: str, data: Any) -> None:
    """Write project JSON as UTF-8 without BOM; non-ASCII keys/values preserved (ensure_ascii=False)."""
    if isinstance(data, dict):
        normalize_project_lift_data(data)
        finalize_project_json_for_save(data)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
