"""
Change tracking utility for Lift Design project files.
Computes differences between baseline and current data, producing human-readable change records.
"""
import copy
from datetime import datetime
from typing import Any, List, Dict, Optional

# Keys to exclude from comparison (metadata, not user data)
EXCLUDED_KEYS = {'ChangeHistory', '_baseline', 'FileName'}

from gui.project_lift_schema import LAYOUT_INFORMATION_FIELD_KEYS

# Backwards-compatible alias (layout fields split from legacy ``LiftSystems``)
LIFT_SYSTEMS_LAYOUT_FIELDS = LAYOUT_INFORMATION_FIELD_KEYS

# Map data section keys to sidebar page names (legacy LiftSystems resolved per-field in _path_to_page)
SECTION_TO_PAGE = {
    "BuildingSystems": "1. Building System Information",
    "GeneralSpecification": "2. General specification",
    "LayoutInformation": "3. Layout Information",
    "LiftDrive": "4. Electrical & HVAC",
    "Forces": "5. Mechanical loading",
    "Compliance": "6. Applicable codes",
    "Emergency": "7. Technical Interfaces",
    "Floors": "8. Building Floor Levels",
    "Cost": "9. Cost",
}


def _normalize_value(val: Any) -> Any:
    """Normalize values for comparison (e.g. bool vs int, str numbers)."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    if isinstance(val, str):
        # Try to preserve type for display
        return val
    return val


def _format_value(val: Any) -> str:
    """Format a value for display in the change history."""
    if val is None:
        return "(empty)"
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else "(empty)"
    return str(val)


def _compute_changes_recursive(
    old_obj: Any,
    new_obj: Any,
    path: str,
    changes: List[Dict[str, Any]],
    field_display_map: Optional[Dict[str, str]] = None
) -> None:
    """
    Recursively compare old and new data structures, appending changes to the list.
    """
    if path and field_display_map is not None:
        field_display_map[path] = _path_to_display_name(path)

    if isinstance(old_obj, dict) and isinstance(new_obj, dict):
        all_keys = set(old_obj.keys()) | set(new_obj.keys())
        for key in all_keys:
            if key in EXCLUDED_KEYS:
                continue
            new_path = f"{path}.{key}" if path else key
            old_val = old_obj.get(key)
            new_val = new_obj.get(key)

            if key not in old_obj:
                # Added
                if isinstance(new_val, (dict, list)) and new_val:
                    _compute_changes_recursive({}, new_val, new_path, changes, field_display_map)
                else:
                    changes.append({
                        "field": new_path,
                        "old_value": None,
                        "new_value": _normalize_value(new_val),
                    })
            elif key not in new_obj:
                # Removed
                changes.append({
                    "field": new_path,
                    "old_value": _normalize_value(old_val),
                    "new_value": None,
                })
            else:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    _compute_changes_recursive(old_val, new_val, new_path, changes, field_display_map)
                elif isinstance(old_val, list) and isinstance(new_val, list):
                    # Compare list elements - for our structure, lists are of dicts (e.g. BuildingSystems, Floors)
                    max_len = max(len(old_val), len(new_val))
                    for i in range(max_len):
                        elem_path = f"{new_path}[{i}]"
                        if i >= len(old_val):
                            _compute_changes_recursive({}, new_val[i] if i < len(new_val) else {}, elem_path, changes, field_display_map)
                        elif i >= len(new_val):
                            _compute_changes_recursive(old_val[i], {}, elem_path, changes, field_display_map)
                        else:
                            if isinstance(old_val[i], dict) and isinstance(new_val[i], dict):
                                _compute_changes_recursive(old_val[i], new_val[i], elem_path, changes, field_display_map)
                            elif old_val[i] != new_val[i]:
                                changes.append({
                                    "field": elem_path,
                                    "old_value": _normalize_value(old_val[i]),
                                    "new_value": _normalize_value(new_val[i]),
                                })
                else:
                    if old_val != new_val:
                        changes.append({
                            "field": new_path,
                            "old_value": _normalize_value(old_val),
                            "new_value": _normalize_value(new_val),
                        })
    elif isinstance(old_obj, list) and isinstance(new_obj, list):
        # Fallback for top-level list
        for i, (o, n) in enumerate(zip(old_obj, new_obj)):
            elem_path = f"{path}[{i}]" if path else f"[{i}]"
            _compute_changes_recursive(o, n, elem_path, changes, field_display_map)


def _path_to_display_name(path: str) -> str:
    """Convert a field path to a human-readable display name."""
    # Handle paths like "BuildingSystems.0.System Name" -> "Building System 1 - System Name"
    # Or "Floors.0.Lift 1.0.Floor Name" -> "Lift 1, Floor 0 - Floor Name"
    parts = path.replace("[", ".").replace("]", "").split(".")
    display_parts = []
    section_names = {
        "BuildingSystems": "Building System",
        "GeneralSpecification": "General specification",
        "LayoutInformation": "Layout Information",
        "LiftSystems": "Lift System",
        "LiftDrive": "Electrical & HVAC",
        "Forces": "Force",
        "Compliance": "Compliance",
        "Emergency": "Technical Interfaces",
        "Floors": "Floor",
        "Cost": "Cost",
    }
    i = 0
    while i < len(parts):
        part = parts[i]
        if part in section_names and i + 1 < len(parts):
            try:
                idx = int(parts[i + 1])
                display_parts.append(f"{section_names[part]} {idx + 1}")
                i += 2
            except ValueError:
                display_parts.append(section_names.get(part, part))
                i += 1
        elif part.startswith("Lift ") and i + 1 < len(parts):
            # "Lift 1" with floor index
            display_parts.append(part)
            try:
                floor_idx = int(parts[i + 1])
                display_parts.append(f"Floor {floor_idx}")
                i += 2
            except (ValueError, IndexError):
                i += 1
        elif part.isdigit() and not display_parts:
            i += 1  # Skip standalone indices
        elif part.isdigit():
            i += 1
        else:
            display_parts.append(part)
            i += 1
    return " - ".join(display_parts) if display_parts else path


def _path_to_page(path: str) -> str:
    """Extract the page name from a field path (e.g. 'BuildingSystems.0.X' -> '1. Building System Information')."""
    if not path:
        return ""
    normalized = path.replace("[", ".").replace("]", "")
    parts = [p for p in normalized.split(".") if p]
    if not parts:
        return ""
    first = parts[0]
    if first == "GeneralSpecification":
        return "2. General specification"
    if first == "LayoutInformation":
        return "3. Layout Information"
    if first == "LiftSystems" and len(parts) >= 3:
        field_key = parts[-1]
        if field_key in LIFT_SYSTEMS_LAYOUT_FIELDS:
            return "3. Layout Information"
        return "2. General specification"
    return SECTION_TO_PAGE.get(first, "")


def compute_changes(baseline: Dict, current: Dict) -> List[Dict[str, Any]]:
    """
    Compute the list of changes between baseline and current data.
    Returns a list of dicts with keys: field, field_display, old_value, new_value
    """
    changes = []
    field_display_map = {}
    _compute_changes_recursive(baseline, current, "", changes, field_display_map)

    # Add display names to each change
    for change in changes:
        change["field_display"] = _path_to_display_name(change["field"])

    return changes


def prepare_baseline(data: Dict) -> Dict:
    """Create a clean baseline copy for comparison (excludes metadata)."""
    from gui.project_lift_schema import normalize_project_lift_data

    baseline = {}
    for key, value in data.items():
        if key not in EXCLUDED_KEYS:
            baseline[key] = copy.deepcopy(value)
    normalize_project_lift_data(baseline)
    return baseline


def create_change_records(changes: List[Dict], date: Optional[datetime] = None) -> List[Dict]:
    """
    Convert raw changes to persisted change records with date.
    """
    if date is None:
        date = datetime.now()
    date_str = date.strftime("%Y-%m-%d %H:%M:%S")

    return [
        {
            "field": c["field"],
            "field_display": c["field_display"],
            "page": _path_to_page(c["field"]),
            "old_value": _format_value(c["old_value"]),
            "new_value": _format_value(c["new_value"]),
            "date": date_str,
        }
        for c in changes
    ]
