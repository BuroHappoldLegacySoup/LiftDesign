"""
Per-page lift data in project JSON.

Legacy projects stored general specification and layout in one ``LiftSystems`` list per lift.
New projects use:

- ``GeneralSpecification`` — General specification page fields only (one dict per lift).
- ``LayoutInformation`` — Layout Information page fields only (one dict per lift).

:func:`normalize_project_lift_data` splits legacy ``LiftSystems`` on load; :func:`merged_lift_at`
combines both dicts for code that needs a single merged view (export, derived calculations).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping

# Top-level JSON keys
KEY_GENERAL_SPECIFICATION = "GeneralSpecification"
KEY_LAYOUT_INFORMATION = "LayoutInformation"
KEY_LIFT_SYSTEMS_LEGACY = "LiftSystems"

# Must match ``layout_information_page.LayoutInformationPage.LAYOUT_DESCRIPTIONS`` keys.
LAYOUT_INFORMATION_FIELD_KEYS = frozenset({
    'Cabin type/shape',
    'Cabin width (mm)', 'Cabin depth (mm)',
    'Cladding thickness each wall (mm)',
    'Clear cabin height (mm)', 'Structural cabin height (mm)', 'Door width (mm)',
    'Door structural opening width (mm)', 'Door height (mm)', 'Door structural opening height (mm)',
    'door type', 'door fixation type', 'Permissible sill load / Loading class', 'LOP type and locaion',
    'LIP type and location', 'Lift maintenance panel type', 'Lift maintenance panel location',
    'Shaft equipment fixation type', 'Shaft width suggested (mm)', 'Shaft width current planning (mm)',
    'Shaft division type', 'Shaft division width (mm)', 'Shaft depth suggested (mm)',
    'Shaft depth current planning (mm)', 'Shaft head suggested (mm)', 'Shaft head current planning (mm)',
    'Shaft pit suggested (mm)', 'Shaft pit current planning (mm)', 'Machine room width suggested (mm)',
    'Machine room width current planning (mm)', 'Machine room depth suggested (mm)',
    'Machine room depth current planning (mm)',
    'Machine room height suggested (mm)', 'Machine room height current planning (mm)',
    'Lift vestibule width (mm)', 'Lift vestibule depth (mm)',
})


def split_legacy_lift_systems_entry(entry: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Split one legacy combined lift dict into general-spec vs layout dicts."""
    general: Dict[str, Any] = {}
    layout: Dict[str, Any] = {}
    for k, v in entry.items():
        if k in LAYOUT_INFORMATION_FIELD_KEYS:
            layout[k] = v
        else:
            general[k] = v
    return general, layout


def _align_lift_lists_to_building_systems(data: MutableMapping[str, Any]) -> None:
    n = len(data.get('BuildingSystems') or [])
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
