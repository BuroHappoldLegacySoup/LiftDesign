"""
Per-page lift data in project JSON.

Legacy projects stored general specification and layout in one ``LiftSystems`` list per lift.
New projects use:

- ``GeneralSpecification`` — General specification page fields only (one dict per lift). Keys are
  **unit-free** (e.g. ``"Load capacity"`` / ``"Speed"``); units are shown only in the UI Unit column.
- ``LayoutInformation`` — Layout Information page fields only (one dict per lift). Keys are
  unit-free (e.g. ``Cabin width``); units appear only in the UI Unit column.

:func:`normalize_project_lift_data` splits legacy ``LiftSystems`` on load; :func:`merged_lift_at`
combines both dicts for code that needs a single merged view (export, derived calculations).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Sequence

# Building System page: consecutive lift columns merged under group headers; sums to ``len(BuildingSystems)``.
KEY_LIFT_COLUMN_GROUPS = "LiftColumnGroups"


def parse_lift_column_groups(raw: Any, n_lifts: int) -> List[Dict[str, Any]]:
    """
    Normalize JSON (or in-memory list) to ``[{"name": str, "count": int}, ...]`` summing to ``n_lifts``.

    Used by the Building System UI, LD Excel export grouping, and the lift-groups dialog.
    """
    out: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for x in raw:
            if not isinstance(x, dict):
                continue
            try:
                cnt = int(x.get("count", 0))
            except (TypeError, ValueError):
                cnt = 0
            name = str(x.get("name", "") or "").strip()
            if cnt > 0:
                out.append({"name": name, "count": cnt})
    if sum(g["count"] for g in out) == n_lifts and out:
        return out
    return [{"name": f"Group {i + 1}", "count": 1} for i in range(max(0, n_lifts))]


def _normalized_lift_group_title(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def merge_consecutive_lift_groups_same_name(
    groups: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge **adjacent** group entries when titles match case-insensitively (same logical group).

    Used by LD export when stored ``LiftColumnGroups`` repeated one row per lift even though the
    Building System table showed one merged header for several lifts with the same name.
    """
    merged: List[Dict[str, Any]] = []
    for g in groups:
        try:
            cnt = int(g.get("count", 0))
        except (TypeError, ValueError):
            cnt = 0
        if cnt <= 0:
            continue
        name = str(g.get("name", "") or "").strip()
        key = _normalized_lift_group_title(name)
        if merged and _normalized_lift_group_title(str(merged[-1].get("name", ""))) == key:
            merged[-1]["count"] = int(merged[-1]["count"]) + cnt
        else:
            merged.append({"name": name, "count": cnt})
    return merged


# Legacy ``GeneralSpecification`` keys (units / Stck. in the key) → canonical keys (value-only; units are not in the key).
# Canonical names match the Description column on the General specification page; units live in the separate Unit column.
LEGACY_GENERAL_SPEC_KEY_TO_CANONICAL: Dict[str, str] = {
    "Load capacity (kg)": "Load capacity",
    "Permissible number of persons (Pers.)": "Permissible number of persons",
    "Speed (m/s)": "Speed",
    "Acceleration (m/s²)": "Acceleration",
    "Acceleration (m/s2)": "Acceleration",
    "Acceleration (m/s^2)": "Acceleration",
    "Jerk (m/s³)": "Jerk",
    "Jerk (m/s3)": "Jerk",
    "Jerk (m/s^3)": "Jerk",
    "Travel height (m)": "Travel height",
    "Stops (Stck.)": "Stops",
    "Number of floors (Stck.)": "Number of floors",
    "Number of shaft doors (Stck.)": "Number of shaft doors",
    "Acces type": "Access type",
    "Accesible rooms/cwt safety (y/n)": "Accessible rooms/cwt safety",
    "Accessible rooms/cwt safety (y/n)": "Accessible rooms/cwt safety",
}


def migrate_dict_keys_canonical(d: Dict[str, Any], legacy_map: Mapping[str, str]) -> None:
    """Rename dict keys using ``legacy_map`` (old → new), preferring non-empty new values (in place)."""
    if not isinstance(d, dict) or not d:
        return
    for old_k in list(d.keys()):
        if not isinstance(old_k, str):
            continue
        new_k = legacy_map.get(old_k, old_k)
        if new_k == old_k:
            continue
        if old_k not in d:
            continue
        old_v = d[old_k]
        new_v = d.get(new_k)
        if _is_empty_lift_field_value(new_v) and not _is_empty_lift_field_value(old_v):
            d[new_k] = old_v
        elif new_k not in d:
            d[new_k] = old_v
        del d[old_k]


# --- Layout Information: legacy keys (with units in the key) → canonical (unit-free) ---

LEGACY_LAYOUT_KEY_TO_CANONICAL: Dict[str, str] = {
    'Cabin width (mm)': 'Cabin width',
    'Cabin depth (mm)': 'Cabin depth',
    'Cladding thickness each wall (mm)': 'Cladding thickness each wall',
    'Clear cabin height (mm)': 'Clear cabin height',
    'Structural cabin height (mm)': 'Structural cabin height',
    'Door width (mm)': 'Door width',
    'Door structural opening width (mm)': 'Door structural opening width',
    'Door height (mm)': 'Door height',
    'Door structural opening height (mm)': 'Door structural opening height',
    'Shaft width suggested (mm)': 'Shaft width suggested',
    'Shaft width current planning (mm)': 'Shaft width current planning',
    'Shaft division width (mm)': 'Shaft division width',
    'Shaft depth suggested (mm)': 'Shaft depth suggested',
    'Shaft depth current planning (mm)': 'Shaft depth current planning',
    'Shaft head suggested (mm)': 'Shaft head suggested',
    'Shaft head current planning (mm)': 'Shaft head current planning',
    'Shaft pit suggested (mm)': 'Shaft pit suggested',
    'Shaft pit current planning (mm)': 'Shaft pit current planning',
    'Machine room width suggested (mm)': 'Machine room width suggested',
    'Machine room width current planning (mm)': 'Machine room width current planning',
    'Machine room depth suggested (mm)': 'Machine room depth suggested',
    'Machine room depth current planning (mm)': 'Machine room depth current planning',
    'Machine room height suggested (mm)': 'Machine room height suggested',
    'Machine room height current planning (mm)': 'Machine room height current planning',
    'Lift vestibule width (mm)': 'Lift vestibule width',
    'Lift vestibule depth (mm)': 'Lift vestibule depth',
    'LOP type and locaion': 'LOP type and location',
}

LAYOUT_INFORMATION_FIELD_KEYS = frozenset({
    'Cabin type/shape',
    'Cabin width',
    'Cabin depth',
    'Cladding thickness each wall',
    'Clear cabin height',
    'Structural cabin height',
    'Door width',
    'Door structural opening width',
    'Door height',
    'Door structural opening height',
    'door type',
    'door fixation type',
    'Permissible sill load / Loading class',
    'LOP type and location',
    'LIP type and location',
    'Lift maintenance panel type',
    'Lift maintenance panel location',
    'Shaft equipment fixation type',
    'Shaft width suggested',
    'Shaft width current planning',
    'Shaft division type',
    'Shaft division width',
    'Shaft depth suggested',
    'Shaft depth current planning',
    'Shaft head suggested',
    'Shaft head current planning',
    'Shaft pit suggested',
    'Shaft pit current planning',
    'Machine room width suggested',
    'Machine room width current planning',
    'Machine room depth suggested',
    'Machine room depth current planning',
    'Machine room height suggested',
    'Machine room height current planning',
    'Lift vestibule width',
    'Lift vestibule depth',
})


# --- LiftDrive (Electrical & HVAC) ---

LEGACY_LIFT_DRIVE_KEY_TO_CANONICAL: Dict[str, str] = {
    'Number of trips per hour (1/h)': 'Number of trips per hour',
    'Power grid voltage/type (V)': 'Power grid voltage/type',
    'Duty cycle (motor) (%)': 'Duty cycle (motor)',
    'Drive/Motor Power (kW)': 'Drive/Motor Power',
    'Connected load (kVA)': 'Connected load',
    'Rated current (A)': 'Rated current',
    'Starting current (factor ≈ 2) (A)': 'Starting current (factor ≈ 2)',
    'Energy recovery (y/n)': 'Energy recovery',
    'Diversity factor (-)': 'Diversity factor',
    'Energy consumption (kWh)': 'Energy consumption',
    'Heat dissipation motor (kJ)': 'Heat dissipation motor',
    'Temperature machine room / shaft (°C)': 'Temperature machine room / shaft',
}


# --- Forces (Mechanical loading) ---

LEGACY_FORCES_KEY_TO_CANONICAL: Dict[str, str] = {
    'Rail weight car (kg/m)': 'Rail weight car',
    'Force F1, F2 elevator rail segment (kN)': 'Force F1, F2 elevator rail segment',
    'Number of car buffers (St.)': 'Number of car buffers',
    'Force F3, each buffer (kN)': 'Force F3, each buffer',
    'Number of cwt buffers (St.)': 'Number of cwt buffers',
    'Rail weight cwt (kg/m)': 'Rail weight cwt',
    'Force F4, per counterweight rail segment (kN)': 'Force F4, per counterweight rail segment',
    'Force F5, per counterweight buffer (kN)': 'Force F5, per counterweight buffer',
    'Force F6, static shaft door (kN)': 'Force F6, static shaft door',
    'Force F7, static counterweight (kN)': 'Force F7, static counterweight',
    'Force F8, static cabin (kN)': 'Force F8, static cabin',
    'Force Fx, cabin rail (kN)': 'Force Fx, cabin rail',
    'Force Fy, cabin rail (kN)': 'Force Fy, cabin rail',
    'Force Fx, counterweight rail (kN)': 'Force Fx, counterweight rail',
    'Force Fy, counterweight rail (kN)': 'Force Fy, counterweight rail',
}


# --- Emergency (Technical Interfaces) ---

LEGACY_EMERGENCY_KEY_TO_CANONICAL: Dict[str, str] = {
    'Smoke management type (type)': 'Smoke management type',
    'Smoke extraction min. size netto (mm²)': 'Smoke extraction min. size netto',
    'FAS interfaces as per spec (y/n)': 'FAS interfaces as per spec',
    'Main evacuation floor fire return and EEL EN81-76 (floor no.)': 'Main evacuation floor fire return and EEL EN81-76',
    'Alternate evacuation floor (floor no.)': 'Alternate evacuation floor',
    'Emergency power (y/n)': 'Emergency power',
    'Cascading evacuation control (y/n)': 'Cascading evacuation control',
    'Type of emergency power (type)': 'Type of emergency power',
    'FCC panel interface as per spec (y/n)': 'FCC panel interface as per spec',
    '2-way intercom firefighter lift (y/n)': '2-way intercom firefighter lift',
    'self-rescue method firefighter lift (type)': 'self-rescue method firefighter lift',
    'BMS interfaces as per spec (y/n)': 'BMS interfaces as per spec',
    'lift monitoring (y/n)': 'lift monitoring',
    'ICT/AV interfaces as per spec (y/n)': 'ICT/AV interfaces as per spec',
    'Access Control interface as per spec (y/n)': 'Access Control interface as per spec',
    'other Security interfaces as per spec. (y/n)': 'other Security interfaces as per spec.',
    'PAVA alarm interface car (y/n)': 'PAVA alarm interface car',
    'Sprinkler in shaft / Shunt trip (y/n)': 'Sprinkler in shaft / Shunt trip',
    'Water management Firefighter and Evacuation lift (type)': 'Water management Firefighter and Evacuation lift',
    'other functions (type)': 'other functions',
}


# Top-level JSON keys
KEY_GENERAL_SPECIFICATION = "GeneralSpecification"
KEY_LAYOUT_INFORMATION = "LayoutInformation"
KEY_LIFT_SYSTEMS_LEGACY = "LiftSystems"
KEY_FLOORS = "Floors"


def _align_floors_list_to_building_systems(data: MutableMapping[str, Any]) -> None:
    """Pad ``Floors`` so there is one entry per building lift (stable load/save round-trip)."""
    n = len(data.get("BuildingSystems") or [])
    if n == 0:
        return
    floors = data.get(KEY_FLOORS)
    if not isinstance(floors, list):
        data[KEY_FLOORS] = [{f"Lift {i + 1}": []} for i in range(n)]
        return
    while len(floors) < n:
        floors.append({f"Lift {len(floors) + 1}": []})


def _general_spec_has_floor_row_count(entry: Dict[str, Any]) -> bool:
    """True if **Number of floors** or **Stops** (canonical or legacy) is set to a positive integer."""
    for key in (
        "Number of floors",
        "Stops",
        "Number of floors (Stck.)",
        "Stops (Stck.)",
    ):
        raw = entry.get(key, "")
        if raw is None or not str(raw).strip():
            continue
        try:
            n = int(str(raw).strip())
            if n >= 1:
                return True
        except (ValueError, TypeError):
            continue
    return False


def _backfill_num_floors_from_floors_list(data: MutableMapping[str, Any]) -> None:
    """When **Number of floors** is blank but ``Floors`` has rows (e.g. after copy), sync the count.

    Without this, the building floor table assumes one row, reload looks like data loss, and saves
    can overwrite the copied JSON with a single blank row.
    """
    gen = data.get(KEY_GENERAL_SPECIFICATION)
    floors = data.get(KEY_FLOORS)
    if not isinstance(gen, list) or not isinstance(floors, list):
        return
    for i in range(min(len(gen), len(floors))):
        gi = gen[i]
        if not isinstance(gi, dict):
            continue
        if _general_spec_has_floor_row_count(gi):
            continue
        fi = floors[i]
        if not isinstance(fi, dict):
            continue
        key = f"Lift {i + 1}"
        lst = fi.get(key)
        if not isinstance(lst, list) or len(lst) < 1:
            continue
        gi["Number of floors"] = str(len(lst))


def split_legacy_lift_systems_entry(entry: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Split one legacy combined lift dict into general-spec vs layout dicts."""
    general: Dict[str, Any] = {}
    layout: Dict[str, Any] = {}
    for k, v in entry.items():
        ck = LEGACY_LAYOUT_KEY_TO_CANONICAL.get(k, k)
        if ck in LAYOUT_INFORMATION_FIELD_KEYS:
            layout[ck] = v
        else:
            general[ck] = v
    return general, layout


def _is_empty_lift_field_value(v: Any) -> bool:
    """Treat None and blank strings as missing so legacy ``LiftSystems`` can fill them."""
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == '':
        return True
    return False


def migrate_general_specification_dict(d: Dict[str, Any]) -> None:
    """Rewrite known legacy keys to canonical keys (in place)."""
    migrate_dict_keys_canonical(d, LEGACY_GENERAL_SPEC_KEY_TO_CANONICAL)


def _merge_lift_dict_prefer_non_empty(existing: Dict[str, Any], legacy_split: Dict[str, Any]) -> Dict[str, Any]:
    """Start from legacy split, then overwrite with any non-empty values from ``existing``."""
    out = dict(legacy_split)
    for k, v in existing.items():
        if not _is_empty_lift_field_value(v):
            out[k] = v
    return out


def _align_lift_lists_to_building_systems(data: MutableMapping[str, Any]) -> None:
    """Pad or trim per-lift lists so lengths match, without wiping saved sections.

    Using only ``len(BuildingSystems)`` could set *n* to 0 (e.g. empty list) and **pop** all
    ``GeneralSpecification`` / ``LayoutInformation`` entries, which then makes the UI fall back
    to defaults and overwrite JSON on sync.
    """
    n_build = len(data.get('BuildingSystems') or [])
    gen = data.get(KEY_GENERAL_SPECIFICATION)
    lay = data.get(KEY_LAYOUT_INFORMATION)
    n_gen = len(gen) if isinstance(gen, list) else 0
    n_lay = len(lay) if isinstance(lay, list) else 0
    n = max(n_build, n_gen, n_lay)
    for key in (KEY_GENERAL_SPECIFICATION, KEY_LAYOUT_INFORMATION):
        lst = data.get(key)
        if not isinstance(lst, list):
            data[key] = [{} for _ in range(n)]
            continue
        while len(lst) < n:
            lst.append({})
        while len(lst) > n:
            lst.pop()


def normalize_project_lift_data(data: MutableMapping[str, Any]) -> None:
    """Ensure ``GeneralSpecification`` / ``LayoutInformation`` exist; migrate legacy ``LiftSystems``."""
    if not isinstance(data, dict):
        return

    legacy = data.get(KEY_LIFT_SYSTEMS_LEGACY)
    gen = data.get(KEY_GENERAL_SPECIFICATION)
    lay = data.get(KEY_LAYOUT_INFORMATION)

    if isinstance(legacy, list) and len(legacy) > 0:
        if not isinstance(gen, list) or len(gen) == 0:
            gen_list: List[Dict[str, Any]] = []
            lay_list: List[Dict[str, Any]] = []
            for entry in legacy:
                if not isinstance(entry, dict):
                    gen_list.append({})
                    lay_list.append({})
                else:
                    g, l = split_legacy_lift_systems_entry(entry)
                    gen_list.append(g)
                    lay_list.append(l)
            data[KEY_GENERAL_SPECIFICATION] = gen_list
            data[KEY_LAYOUT_INFORMATION] = lay_list
        else:
            # Both legacy and split sections exist: merge so we do not drop fields that only live
            # on ``LiftSystems`` (e.g. sparse ``GeneralSpecification`` saved next to a full legacy list).
            if not isinstance(lay, list):
                lay = []
            n_merge = max(len(legacy), len(gen), len(lay))
            while len(gen) < n_merge:
                gen.append({})
            while len(lay) < n_merge:
                lay.append({})
            for i, entry in enumerate(legacy):
                if not isinstance(entry, dict):
                    continue
                g_leg, l_leg = split_legacy_lift_systems_entry(entry)
                gi = gen[i] if isinstance(gen[i], dict) else {}
                li = lay[i] if isinstance(lay[i], dict) else {}
                gen[i] = _merge_lift_dict_prefer_non_empty(gi, g_leg)
                lay[i] = _merge_lift_dict_prefer_non_empty(li, l_leg)
            data[KEY_GENERAL_SPECIFICATION] = gen
            data[KEY_LAYOUT_INFORMATION] = lay
        try:
            del data[KEY_LIFT_SYSTEMS_LEGACY]
        except KeyError:
            pass
    elif legacy is not None:
        try:
            del data[KEY_LIFT_SYSTEMS_LEGACY]
        except KeyError:
            pass

    if not isinstance(data.get(KEY_GENERAL_SPECIFICATION), list):
        data[KEY_GENERAL_SPECIFICATION] = []
    if not isinstance(data.get(KEY_LAYOUT_INFORMATION), list):
        data[KEY_LAYOUT_INFORMATION] = []

    _align_lift_lists_to_building_systems(data)
    _align_floors_list_to_building_systems(data)

    gen = data.get(KEY_GENERAL_SPECIFICATION)
    if isinstance(gen, list):
        for entry in gen:
            if isinstance(entry, dict):
                migrate_general_specification_dict(entry)

    _backfill_num_floors_from_floors_list(data)

    lay_m = data.get(KEY_LAYOUT_INFORMATION)
    if isinstance(lay_m, list):
        for entry in lay_m:
            if isinstance(entry, dict):
                migrate_dict_keys_canonical(entry, LEGACY_LAYOUT_KEY_TO_CANONICAL)

    lift_drive = data.get('LiftDrive')
    if isinstance(lift_drive, list):
        for entry in lift_drive:
            if isinstance(entry, dict):
                migrate_dict_keys_canonical(entry, LEGACY_LIFT_DRIVE_KEY_TO_CANONICAL)

    forces_m = data.get('Forces')
    if isinstance(forces_m, list):
        for entry in forces_m:
            if isinstance(entry, dict):
                migrate_dict_keys_canonical(entry, LEGACY_FORCES_KEY_TO_CANONICAL)

    emergency_m = data.get('Emergency')
    if isinstance(emergency_m, list):
        for entry in emergency_m:
            if isinstance(entry, dict):
                migrate_dict_keys_canonical(entry, LEGACY_EMERGENCY_KEY_TO_CANONICAL)


def finalize_project_json_for_save(data: MutableMapping[str, Any]) -> None:
    """Drop legacy key when the split sections are used (clean saved files)."""
    if not isinstance(data, dict):
        return
    if KEY_GENERAL_SPECIFICATION in data or KEY_LAYOUT_INFORMATION in data:
        data.pop(KEY_LIFT_SYSTEMS_LEGACY, None)


def merged_lift_at(data: Mapping[str, Any], idx: int) -> Dict[str, Any]:
    """Single merged dict for lift ``idx`` (general + layout). Read-only merge."""
    if not isinstance(data, dict):
        return {}
    gen = data.get(KEY_GENERAL_SPECIFICATION) or []
    lay = data.get(KEY_LAYOUT_INFORMATION) or []
    g: Dict[str, Any] = dict(gen[idx]) if 0 <= idx < len(gen) and isinstance(gen[idx], dict) else {}
    l: Dict[str, Any] = dict(lay[idx]) if 0 <= idx < len(lay) and isinstance(lay[idx], dict) else {}
    out = {**g, **l}
    return out


def ensure_lift_section_slots(user_inputs: MutableMapping[str, Any], n_lifts: int) -> None:
    """Pad or trim ``GeneralSpecification`` / ``LayoutInformation`` to ``n_lifts`` entries."""
    normalize_project_lift_data(user_inputs)
    n = max(n_lifts, len(user_inputs.get('BuildingSystems') or []))
    for key in (KEY_GENERAL_SPECIFICATION, KEY_LAYOUT_INFORMATION):
        lst = user_inputs.get(key)
        if not isinstance(lst, list):
            user_inputs[key] = [{} for _ in range(n)]
            continue
        while len(lst) < n:
            lst.append({})
        while len(lst) > n:
            lst.pop()
