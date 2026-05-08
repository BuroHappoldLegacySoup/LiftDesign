"""
Port of the ``VT standard configurations`` **column M..U** formulas so the LD export
can auto-fill derived parameter values from the UI inputs.

The workbook stores a complete design-parameter cascade — cabin geometry, shaft head/pit,
drive electrical (connected load, rated current, heat dissipation), mechanical forces
(F1..F8, Fx/Fy), door types and car-wall thicknesses, COP/handrail positions, and the
shaft-arrangement (wall-distance) lookup. Each column represents one standard config;
the formulas share the same shape, only constants differ per load family.

``compute_derived(user_inputs, lift_index)`` returns a ``Dict[str, str]`` keyed by a
**normalized parameter label** (lowercased, whitespace-collapsed) — the same key the
LD export uses when matching VT row A (``Parameter``) to a resolver. Values are strings
ready to go into the LD workbook. ``build_ld_rows_from_user_inputs`` uses this as a
**fallback** when the UI field is empty, so user-entered values keep priority.

Implementations reuse :mod:`gui.lift_types` (load-profile classes) where possible and
port the remaining VT formulas inline (door opening width, rear-door mirror, COP, wall
distances, car wall thickness, CWT layout).
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from gui.lift_types import (
    electrical_hvac_derived_for_lift,
    load_profile_for_capacity,
    mechanical_loading_derived_for_lift,
)
from gui.project_lift_schema import merged_lift_at


__all__ = [
    "compute_derived",
    "DOOR_MANUFACTURER_COMMON",
    "DOOR_MANUFACTURER_MEILLER",
    "DOOR_MANUFACTURER_OPTIONS",
    "DEFAULT_DOOR_MANUFACTURER",
    "normalize_door_manufacturer",
]


# --- Door manufacturer lookup tables (port of VT 'selection' sheet) ----------
#
# Mirrors ``selection!C94:G104`` / ``selection!K94:O110`` (entrance doors RIDs)
# and the corresponding cabin-door blocks. Values come straight from the VT
# workbook; ``None`` means *no LD product for this combination*, matching the
# Excel "no doors" / blank cells. The order across each row is the canonical
# door-type order ``("2C", "4C", "6C", "2L", "2R")`` so a single column index
# resolves type → RID for every width row.

DOOR_MANUFACTURER_COMMON: str = "Common component"
DOOR_MANUFACTURER_MEILLER: str = "Meiller"
DOOR_MANUFACTURER_OPTIONS: Tuple[str, str] = (
    DOOR_MANUFACTURER_COMMON,
    DOOR_MANUFACTURER_MEILLER,
)
DEFAULT_DOOR_MANUFACTURER: str = DOOR_MANUFACTURER_COMMON

_DOOR_TYPES: Tuple[str, str, str, str, str] = ("2C", "4C", "6C", "2L", "2R")
_DOOR_NOT_AVAILABLE: str = "Doors dont exist in LD"

# selection!C95:G104 (Common component entrance doors RID by door width)
_COMMON_ENTRANCE_RID: Dict[int, Tuple[Optional[int], ...]] = {
    700:  (1,    8,    15,   43,   55),
    800:  (2,    9,    16,   44,   56),
    900:  (3,    10,   17,   45,   57),
    1000: (4,    11,   18,   46,   58),
    1100: (5,    12,   19,   47,   59),
    1200: (6,    13,   20,   48,   60),
    1500: (None, 14,   None, None, None),
    2000: (7,    None, 21,   None, None),
}

# selection!K95:O110 (Meiller entrance doors RID by door width)
_MEILLER_ENTRANCE_RID: Dict[int, Tuple[Optional[int], ...]] = {
    700:  (1400072, None,    None,    1400681, 1400670),
    800:  (1400073, None,    None,    1400682, 1400671),
    900:  (1400074, None,    None,    1400683, 1400672),
    1000: (1400075, None,    None,    1400684, 1400673),
    1100: (1400076, None,    None,    1400685, 1400674),
    1200: (1400077, 1400092, None,    1400686, 1400675),
    1300: (1400078, 1400093, None,    1400687, 1400676),
    1400: (1400079, 1400094, 1400128, 1400688, 1400677),
    1500: (1400080, 1400095, 1400129, 1400689, 1400678),
    1600: (1400081, 1400096, 1400130, 1400690, 1400679),
    1700: (None,    1400097, 1400131, 1400691, 1400680),
    1800: (None,    1400098, 1400132, None,    None),
    1900: (None,    1400099, 1400133, None,    None),
    2000: (None,    1400100, 1400134, None,    None),
    2100: (None,    1400101, 1400135, None,    None),
    2200: (None,    1400102, 1400136, None,    None),
}

# selection!C107:G107 / K112:O112 (entrance door depth in mm)
_COMMON_ENTRANCE_DEPTH: Dict[str, float] = {"2C": 125, "4C": 150, "6C": 195, "2L": 150, "2R": 150}
_MEILLER_ENTRANCE_DEPTH: Dict[str, float] = {"2C": 120, "4C": 120, "6C": 180, "2L": 98.5, "2R": 98.5}

# selection!C110:G119 (Common component cabin doors RID by door width)
_COMMON_CABIN_RID: Dict[int, Tuple[Optional[int], ...]] = {
    700:  (22,   29,   36,   67,   79),
    800:  (23,   30,   37,   68,   80),
    900:  (24,   31,   38,   69,   81),
    1000: (25,   32,   39,   70,   82),
    1100: (26,   33,   40,   71,   83),
    1200: (27,   34,   41,   72,   84),
    1300: (None, 244,  None, None, None),
    1400: (None, 245,  None, None, None),
    2000: (28,   35,   42,   None, None),
}

# selection!K116:O131 (Meiller cabin doors RID by door width)
_MEILLER_CABIN_RID: Dict[int, Tuple[Optional[int], ...]] = {
    700:  (1400082, None,    None,    1400346, 1400280),
    800:  (1400083, None,    None,    1400347, 1400337),
    900:  (1400084, None,    None,    1400348, 1400338),
    1000: (1400085, None,    None,    1400349, 1400339),
    1100: (1400086, None,    None,    1400350, 1400340),
    1200: (1400087, 1400105, None,    1400351, 1400341),
    1300: (1400088, 1400106, None,    1400352, 1400342),
    1400: (1400089, 1400107, 1400147, 1400353, 1400343),
    1500: (1400090, 1400108, 1400148, 1400354, 1400344),
    1600: (1400091, 1400109, 1400149, 1400355, 1400345),
    1700: (None,    1400110, 1400150, 1400693, 1400346),
    1800: (None,    1400111, 1400151, None,    None),
    1900: (None,    1400112, 1400152, None,    None),
    2000: (None,    1400113, 1400153, None,    None),
    2100: (None,    1400114, 1400154, None,    None),
    2200: (None,    1400115, 1400155, None,    None),
}

# selection!C121:G121 / K134:O134 (cabin door depth in mm)
_COMMON_CABIN_DEPTH: Dict[str, float] = {"2C": 90, "4C": 90, "6C": 135, "2L": 90, "2R": 90}
_MEILLER_CABIN_DEPTH: Dict[str, float] = {"2C": 91, "4C": 91, "6C": 135, "2L": 93, "2R": 93}

# Door / wall clearance: VT R313 / R323 — Common = 25 mm, Meiller = 0 mm.
_DOOR_WALL_CLEARANCE: Dict[str, int] = {
    DOOR_MANUFACTURER_COMMON: 25,
    DOOR_MANUFACTURER_MEILLER: 0,
}


def normalize_door_manufacturer(value: Any) -> str:
    """Map free-form input to one of :data:`DOOR_MANUFACTURER_OPTIONS` (default Common)."""
    s = _s(value).strip().lower()
    if not s:
        return DEFAULT_DOOR_MANUFACTURER
    if "meiller" in s:
        return DOOR_MANUFACTURER_MEILLER
    if "common" in s or "standard" in s or "std" in s:
        return DOOR_MANUFACTURER_COMMON
    return DEFAULT_DOOR_MANUFACTURER


def _mirror_rear_door_type(dt: str) -> str:
    """VT R280/R288 mirror: 2L↔2R, others (2C/4C/6C) pass through unchanged."""
    if dt == "2L":
        return "2R"
    if dt == "2R":
        return "2L"
    if dt in ("2C", "4C", "6C"):
        return dt
    return ""


def _door_rid(
    table: Dict[int, Tuple[Optional[int], ...]],
    door_type: str,
    door_width_mm: Optional[int],
) -> Optional[int]:
    """Resolve (door_type, door_width) → RID using a manufacturer table; ``None`` if absent."""
    if not door_type or door_type not in _DOOR_TYPES or door_width_mm is None:
        return None
    row = table.get(door_width_mm)
    if not row:
        return None
    return row[_DOOR_TYPES.index(door_type)]


# --- small helpers -----------------------------------------------------------

def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v).strip()


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def _to_float(raw: Any) -> Optional[float]:
    t = _s(raw).replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except (ValueError, TypeError):
        return None


def _to_int(raw: Any) -> Optional[int]:
    f = _to_float(raw)
    if f is None:
        return None
    return int(round(f))


def _fmt_int(x: float) -> str:
    return str(int(round(x)))


def _fmt_dim(x: float) -> str:
    if abs(x - round(x)) < 1e-6:
        return str(int(round(x)))
    return str(round(x, 2))


def _field(d: Mapping[str, Any], *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip() != "":
            return _s(v)
    return ""


def _yes(v: Any) -> bool:
    return _s(v).lower() in ("yes", "y", "true", "1")


# --- section resolvers -------------------------------------------------------

def _drive(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("LiftDrive") or []
    return dict(rows[i]) if 0 <= i < len(rows) and isinstance(rows[i], dict) else {}


def _forces(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("Forces") or []
    return dict(rows[i]) if 0 <= i < len(rows) and isinstance(rows[i], dict) else {}


# --- VT R292 / R293 — shaft wall-distance lookup ----------------------------
# Encoded as a shared table: each row matches (cabin_width, door_width, {door_types}).
# ``access_restrict``: ``None`` = any accessibility; ``"yes"`` / ``"no"`` = restricted.
# Cladding is added on top of the base offset (Excel: ``+ M36``).

_WALL_CWT_SIDE: Tuple[Tuple[int, int, Tuple[str, ...], Optional[str], int], ...] = (
    (1100,  900, ("2L", "2R"), None,  450),
    (1600, 1000, ("2C",),      "no",  400),
    (1600, 1000, ("2C",),      "yes", 450),
    (1200, 1100, ("2L", "2R"), None,  600),
    (2000, 1100, ("2C",),      None,  550),
    (1400, 1300, ("4C",),      None,  500),
    (2100, 1300, ("4C",),      "no",  550),
    (2100, 1200, ("2C",),      None,  550),
    (1500, 1300, ("4C",),      None,  575),
    (1800, 1500, ("4C",),      None,  650),
    (2100, 1800, ("4C",),      None,  750),
)

_WALL_NON_CWT_SIDE: Tuple[Tuple[int, int, Tuple[str, ...], Optional[str], int], ...] = (
    (1100,  900, ("2L", "2R"), None,  200),
    (1600, 1000, ("2C",),      None,  300),
    (1200, 1100, ("2L", "2R"), None,  200),
    (2000, 1100, ("2C",),      None,  250),
    (1400, 1300, ("4C",),      None,  400),
    (2100, 1300, ("4C",),      "no",  400),
    (2100, 1200, ("2C",),      None,  250),
    (1500, 1300, ("4C",),      None,  375),
    (1800, 1500, ("4C",),      None,  250),
    (2100, 1800, ("4C",),      None,  430),
)


def _lookup_wall_distance(
    table: Tuple[Tuple[int, int, Tuple[str, ...], Optional[str], int], ...],
    cw_mm: Optional[int],
    dw_mm: Optional[int],
    dt: str,
    accessible_yes: bool,
    cladding_mm: float,
) -> Optional[int]:
    if cw_mm is None or dw_mm is None or not dt:
        return None
    access_key = "yes" if accessible_yes else "no"
    for row_cw, row_dw, row_dts, row_access, base in table:
        if row_cw != cw_mm or row_dw != dw_mm or dt not in row_dts:
            continue
        if row_access is not None and row_access != access_key:
            continue
        return int(round(base + float(cladding_mm)))
    return None


# --- main builder ------------------------------------------------------------

def compute_derived(
    user_inputs: Mapping[str, Any],
    lift_index: int,
    door_manufacturer: Optional[str] = None,
) -> Dict[str, str]:
    """
    Compute VT-formula values for lift ``lift_index``; keys are normalized parameter labels.

    Only returns entries that can be computed from the available UI inputs. Missing entries
    mean "no override" — the LD export should keep the UI value (even if empty).

    ``door_manufacturer`` controls the VT R277 ``Door manufacturer choice`` cell. When
    omitted, falls back to ``user_inputs["DoorManufacturer"]`` and finally to
    :data:`DEFAULT_DOOR_MANUFACTURER`. Any non-canonical string is mapped through
    :func:`normalize_door_manufacturer` so external callers can pass user-typed text.
    """
    if not isinstance(user_inputs, dict):
        return {}
    lift = merged_lift_at(user_inputs, lift_index)
    drive = _drive(user_inputs, lift_index)
    forces = _forces(user_inputs, lift_index)

    # --- raw UI inputs
    load_kg_raw = _field(lift, "Load capacity", "Load capacity (kg)")
    persons_raw = _field(lift, "Permissible number of persons", "Permissible number of persons (Pers.)")
    speed_raw = _field(lift, "Speed", "Speed (m/s)")
    shape = _field(lift, "Cabin type/shape")
    cwt_loc = _field(lift, "Counterweight location")
    access_type = _field(lift, "Access type")
    accessible = _field(lift, "Accessible rooms/cwt safety", "Accessible rooms / cwt safety")
    cladding_raw = _field(lift, "Cladding thickness each wall", "Cladding thickness each wall (mm)")
    clear_h_raw = _field(lift, "Clear cabin height", "Clear cabin height (mm)")
    travel_raw = _field(lift, "Travel height", "Travel height (m)")
    door_width_raw = _field(lift, "Door width", "Door width (mm)")

    cabin_w_ui = _field(lift, "Cabin width", "Cabin width (mm)")
    cabin_d_ui = _field(lift, "Cabin depth", "Cabin depth (mm)")
    struct_h_ui = _field(lift, "Structural cabin height", "Structural cabin height (mm)")
    door_h_ui = _field(lift, "Door height", "Door height (mm)")
    door_type_ui = _field(lift, "Door type", "door type")

    duty_cycle = _field(drive, "Duty cycle (motor)", "Duty cycle (motor) (%)")
    num_car_buf = _field(forces, "Number of car buffers", "Number of car buffers (St.)", "number of car buffers (kg/m)")
    num_cwt_buf = _field(forces, "Number of cwt buffers", "Number of cwt buffers (St.)")
    cwt_safety = _field(forces, "Counterweight safety gear")

    cladding_mm = _to_float(cladding_raw) or 0.0
    accessible_yes = _yes(accessible)

    profile = load_profile_for_capacity(load_kg_raw)

    out: Dict[str, str] = {}

    # -------- R34 cabin width (clear): IF(shape="Deep",...,IF(shape="Wide",...))
    cabin_w_calc = profile.cabin_width_mm(shape)
    if cabin_w_calc and not cabin_w_calc.startswith("non std") and not cabin_w_calc.startswith("Wrong"):
        out["cabin width (clear)"] = cabin_w_calc
        # Alias for VT rows that use the unqualified "Cabin width" label (e.g. R304).
        out["cabin width"] = cabin_w_calc
    cabin_w_used = cabin_w_ui or cabin_w_calc or ""

    # -------- R35 cabin depth (clear): derived from cabin width
    cabin_d_calc = profile.cabin_depth_mm(cabin_w_used)
    if cabin_d_calc and not cabin_d_calc.startswith("non std") and not cabin_d_calc.startswith("non standard"):
        out["cabin depth (clear)"] = cabin_d_calc
        # Alias for VT rows R318/R333/R344 that use the unqualified "Cabin depth" label.
        out["cabin depth"] = cabin_d_calc
    cabin_d_used = cabin_d_ui or cabin_d_calc or ""

    # -------- R38 structural cabin height = clear + 100
    struct_h_calc = profile.structural_cabin_height_mm(clear_h_raw)
    if struct_h_calc:
        out["structural cabin height"] = struct_h_calc
    struct_h_used = struct_h_ui or struct_h_calc or ""

    # -------- R43 door height = clear − 100
    door_h_calc = profile.door_height_mm(clear_h_raw)
    if door_h_calc:
        out["door height"] = door_h_calc
    door_h_used = door_h_ui or door_h_calc or ""

    # -------- R44 door structural opening height = door height + 140
    doh_calc = profile.door_structural_opening_height_mm(door_h_used)
    if doh_calc:
        out["door structural opening height"] = doh_calc

    # -------- R42 door structural opening width = door width + 2*140
    dw_mm = _to_int(door_width_raw)
    if dw_mm is not None:
        out["door structural opening width"] = str(dw_mm + 280)

    # -------- R45 door type (from cabin width + CWT side)
    dt_calc = profile.door_type_code(cabin_w_used, cwt_loc)
    if dt_calc and not dt_calc.startswith("Non std") and not dt_calc.startswith("non std") and not dt_calc.startswith("wrong") and not dt_calc.startswith("Wrong"):
        out["door type"] = dt_calc
    door_type_used = door_type_ui or dt_calc or ""

    # -------- R54 shaft width suggested
    sw = profile.shaft_width_suggested_mm(cabin_w_used, cladding_mm, accessible_yes)
    if sw and not sw.startswith("non"):
        out["shaft width suggested"] = sw

    # -------- R58 shaft depth suggested
    sd = profile.shaft_depth_suggested_mm(cabin_d_used, cladding_mm, access_type)
    if sd and not sd.startswith("non"):
        out["shaft depth suggested"] = sd

    # -------- R60 shaft head suggested
    head = profile.shaft_head_suggested_mm(
        struct_h_used,
        speed_raw,
        cabin_w_used,
        door_width_raw,
        door_type_used,
        cladding_mm,
        accessible_yes,
    )
    if head:
        out["shaft head suggested"] = head

    # -------- R62 shaft pit suggested
    pit = profile.shaft_pit_suggested_mm(speed_raw)
    if pit and not pit.startswith("non"):
        out["shaft pit suggested"] = pit

    # -------- R80..R87 Electrical & HVAC
    elec = electrical_hvac_derived_for_lift(load_kg_raw, persons_raw, duty_cycle)
    if elec:
        if "Drive/Motor Power" in elec:
            out["drive/motor power"] = elec["Drive/Motor Power"]
        if "Connected load" in elec:
            out["connected load"] = elec["Connected load"]
        if "Rated current" in elec:
            out["rated current"] = elec["Rated current"]
        if "Energy consumption" in elec:
            out["energy consumption"] = elec["Energy consumption"]
        if "Heat dissipation motor" in elec:
            out["heat dissipation motor"] = elec["Heat dissipation motor"]

    # -------- R92..R106 Mechanical forces
    travel_m = _to_float(travel_raw) or 0.0
    mech = mechanical_loading_derived_for_lift(
        load_kg_raw,
        travel_m,
        cabin_w_used,
        cabin_d_used,
        _yes(cwt_safety),
        num_car_buf or "2",
        num_cwt_buf or "2",
    )
    for mech_key, derived_key in (
        ("Force F1, F2 elevator rail segment", "force f1, f2 elevator rail segment"),
        ("Force F3, each buffer",              "force f3, each buffer"),
        ("Force F4, per counterweight rail segment", "force f4, per counterweight rail segment"),
        ("Force F5, per counterweight buffer", "force f5, per counterweight buffer"),
        ("Force F6, static shaft door",        "force f6, static shaft door"),
        ("Force F7, static counterweight",     "force f7, static counterweight"),
        ("Force F8, static cabin",             "force f8, static cabin"),
        ("Force Fx, cabin rail",               "force fx, cabin rail"),
        ("Force Fy, cabin rail",               "force fy, cabin rail"),
        ("Force Fx, counterweight rail",       "force fx, counterweight rail"),
        ("Force Fy, counterweight rail",       "force fy, counterweight rail"),
    ):
        if mech_key in mech:
            out[derived_key] = mech[mech_key]
    # VT column A typo "Fy, cabint rail" normalizes separately; mirror to the same value.
    if "force fy, cabin rail" in out:
        out["force fy, cabint rail"] = out["force fy, cabin rail"]

    # -------- R233 COP panel = IF(door_type="2R",3,4)
    if door_type_used:
        cop_panel = 3 if door_type_used == "2R" else 4
        out["cop panel"] = str(cop_panel)

        # -------- R243 Left handrail: IF(cop_panel=4, 44, 8)
        out["left handrail"] = "44" if cop_panel == 4 else "8"
        # -------- R244 Right handrail: literal Excel reads M234; default to 40 unless the
        # computed COP X0 happens to equal 4 (rare / legacy cell).
        out["right handrail"] = "40"

    # -------- R236 Second COP on/off: IF(cabin_width>1600, 40, 44)
    cw_mm = _to_int(cabin_w_used)
    if cw_mm is not None:
        out["second cop"] = "40" if cw_mm > 1600 else "44"

    # -------- R237 Second COP location: IF(cop_panel=4, 3, 40)
    if "cop panel" in out:
        out["second cop location"] = "3" if out["cop panel"] == "4" else "40"

    # -------- R238 Secrond COP length: IF(second_loc=3, 400, IF(second_loc=4, cabin_depth-400, ...))
    cd_mm = _to_int(cabin_d_used)
    loc = out.get("second cop location")
    if loc == "3":
        out["secrond cop length"] = "400"
    elif loc == "4" and cd_mm is not None:
        out["secrond cop length"] = str(cd_mm - 400)

    # -------- R239 Third COP on/off: IF(shape="wide",40,44) — shape compare is case-insensitive in Excel
    if shape:
        is_wide = shape.strip().lower() == "wide"
        out["third cop on/off"] = "40" if is_wide else "44"
        # -------- R240 Third COP location: IF(shape="wide", 1, "doesnt apply")
        out["third cop loaction"] = "1" if is_wide else "doesnt apply"

    # -------- R241 Third COP length = (cabin_width − door_width) / 4
    if cw_mm is not None and dw_mm is not None:
        out["third cop length"] = _fmt_dim((cw_mm - dw_mm) / 4.0)

    # -------- R277 Door manufacturer choice — drives R279/R281/R287/R289 RID lookups
    # and the R313/R323 door/wall clearance + R314/R322/R329/R340 (entrance depth) +
    # R316/R320/R331/R342 (cabin door depth) constants below.
    if door_manufacturer is None:
        door_manufacturer = user_inputs.get("DoorManufacturer")
    manufacturer = normalize_door_manufacturer(door_manufacturer)
    out["door manufacturer choice"] = manufacturer

    # -------- R313 / R323 Door / wall clearance front + rear (Common = 25, Meiller = 0)
    clearance = _DOOR_WALL_CLEARANCE.get(manufacturer)
    if clearance is not None:
        clearance_str = str(clearance)
        # Front clearance label variants seen in VT (R313, R328 — same text).
        out["door / wall clearance front"] = clearance_str
        out["door/wall clearance front"] = clearance_str
        # Rear clearance label variants (VT typo "clearence", trailing space stripped
        # by ``_norm`` already, but slash spacing differs from front).
        out["door/ wall clearence"] = clearance_str
        out["door / wall clearence"] = clearance_str

    # -------- R279 / R281 Shaft doors RID, R287 / R289 Cabin doors RID
    # door type used for the *front* entrance equals the lift's main door type
    # (M278 = M45). Rear entrance/car door mirrors 2L↔2R per VT R280/R288.
    front_door_type = door_type_used or ""
    rear_door_type = _mirror_rear_door_type(front_door_type)

    if manufacturer == DOOR_MANUFACTURER_COMMON:
        entrance_table = _COMMON_ENTRANCE_RID
        cabin_table = _COMMON_CABIN_RID
        entrance_depth_lookup = _COMMON_ENTRANCE_DEPTH
        cabin_depth_lookup = _COMMON_CABIN_DEPTH
    else:
        entrance_table = _MEILLER_ENTRANCE_RID
        cabin_table = _MEILLER_CABIN_RID
        entrance_depth_lookup = _MEILLER_ENTRANCE_DEPTH
        cabin_depth_lookup = _MEILLER_CABIN_DEPTH

    front_entrance_rid = _door_rid(entrance_table, front_door_type, dw_mm)
    rear_entrance_rid = _door_rid(entrance_table, rear_door_type, dw_mm)
    front_car_rid = _door_rid(cabin_table, front_door_type, dw_mm)
    rear_car_rid = _door_rid(cabin_table, rear_door_type, dw_mm)

    if front_door_type:
        out["front entrance"] = (
            str(front_entrance_rid)
            if front_entrance_rid is not None
            else _DOOR_NOT_AVAILABLE
        )
        out["front car doors"] = (
            str(front_car_rid)
            if front_car_rid is not None
            else _DOOR_NOT_AVAILABLE
        )
    if rear_door_type:
        out["rear entrance"] = (
            str(rear_entrance_rid)
            if rear_entrance_rid is not None
            else _DOOR_NOT_AVAILABLE
        )
        out["rear car doors"] = (
            str(rear_car_rid)
            if rear_car_rid is not None
            else _DOOR_NOT_AVAILABLE
        )

    # -------- R314 / R322 / R329 / R340 entrance door depth and
    #          R316 / R320 / R331 / R342 cabin door depth (per door type)
    front_entrance_depth: Optional[float] = None
    front_cabin_depth: Optional[float] = None
    rear_entrance_depth: Optional[float] = None
    rear_cabin_depth: Optional[float] = None
    if front_door_type and front_door_type in entrance_depth_lookup:
        front_entrance_depth = entrance_depth_lookup[front_door_type]
        out["front door depth"] = _fmt_dim(front_entrance_depth)
        rear_entrance_depth = entrance_depth_lookup.get(rear_door_type, front_entrance_depth)
        out["rear door depth"] = _fmt_dim(rear_entrance_depth)
    if front_door_type and front_door_type in cabin_depth_lookup:
        front_cabin_depth = cabin_depth_lookup[front_door_type]
        out["front car door depth"] = _fmt_dim(front_cabin_depth)
        rear_cabin_depth = cabin_depth_lookup.get(rear_door_type, front_cabin_depth)
        out["rear car door depth"] = _fmt_dim(rear_cabin_depth)

    # -------- Shaft-depth section constants (VT R312/R315/R321/R324/R327/R330/R338/R341)
    # These cells are hardcoded in the VT workbook and must always be exported so the
    # downstream LD rows (Shaft0.Entries*.Pocket0.N_T, Shaft0.Car.Door*.DY) are not blank.
    out["front pocket depth"] = "0"
    out["rear pocket depth"] = "0"
    door_clearance_const = 30  # mm — VT hardcoded for both Common and Meiller
    out["door clearance front"] = str(door_clearance_const)
    out["door clearance rear"] = str(door_clearance_const)

    # -------- R334 / R345 front + rear car wall = 25 + cladding (matches R303/R305 left/right)
    car_wall_mm = int(round(25 + cladding_mm))
    out["front car wall"] = str(car_wall_mm)
    out["rear car wall"] = str(car_wall_mm)

    # -------- R356..R359 shaft wall thicknesses (template default = 250 mm)
    for wall_label in ("front wall", "rear wall", "left wall", "right wall"):
        out[wall_label] = "250"

    # -------- R382 / R387 LOP center from wall = 315 mm (template default)
    out["lop center from wall"] = "315"

    # -------- R393 LIP distance from wall opening to LIP center = 175 mm (template default)
    out["lip distance from wall opening to lip center"] = "175"

    # -------- R317 / R319 / R332 / R343 Car return front / rear (H1 / H2)
    # Picks the active formula based on access type so the value matches the LD
    # geometry (Open Through, Front-only, or Rear-only entrance configs). These
    # transitively depend on the manufacturer through the door-depth lookups above
    # — keeping them in sync is the whole reason the manufacturer cell exists.
    sd_str = out.get("shaft depth suggested", "")
    sd_mm = _to_int(sd_str)
    cd_mm_geom = _to_int(cabin_d_used)
    have_geom = sd_mm is not None and cd_mm_geom is not None and clearance is not None
    have_front_depths = front_entrance_depth is not None and front_cabin_depth is not None
    have_rear_depths = rear_entrance_depth is not None and rear_cabin_depth is not None

    access_norm = access_type.strip().lower() if access_type else ""
    open_through = access_norm in ("front + rear", "front+rear", "front + side + rear")
    front_only = access_norm == "front"
    rear_only = access_norm == "rear"

    def _front_pocket_sum() -> Optional[float]:
        if not (have_front_depths and clearance is not None):
            return None
        return 0 + clearance + front_entrance_depth + door_clearance_const + front_cabin_depth

    def _rear_pocket_sum() -> Optional[float]:
        if not (have_rear_depths and clearance is not None):
            return None
        return 0 + clearance + rear_entrance_depth + door_clearance_const + rear_cabin_depth

    front_sum = _front_pocket_sum()
    rear_sum = _rear_pocket_sum()

    # Always compute Open Through values as a baseline (matches VT R311/R317/R319).
    # When access is Front-only or Rear-only, the matching 325-based formula
    # (VT R326/R332 or R337/R343) overrides the baseline so the value lines up with
    # the actual lift geometry. Both H1 and H2 are emitted so neither LD path is
    # left blank — a single-entrance lift still gets a sensible value on the
    # opposite side rather than an empty cell.
    open_through_base: Optional[float] = None
    if have_geom:
        open_through_base = (sd_mm - cd_mm_geom) / 2.0

    car_return_front: Optional[float] = None
    car_return_rear: Optional[float] = None
    if open_through_base is not None and front_sum is not None:
        car_return_front = open_through_base - front_sum
    if open_through_base is not None and rear_sum is not None:
        car_return_rear = open_through_base - rear_sum
    if front_only and front_sum is not None:
        car_return_front = 325.0 - front_sum
    if rear_only and rear_sum is not None:
        car_return_rear = 325.0 - rear_sum

    if car_return_front is not None:
        out["car return front"] = _fmt_dim(car_return_front)
    if car_return_rear is not None:
        out["car return rear"] = _fmt_dim(car_return_rear)
        # VT R343 carries the typo label "Rear return front" — alias so that VT row
        # also resolves to the same value.
        out["rear return front"] = _fmt_dim(car_return_rear)

    # -------- R335 / R346 Rear / Front distance wall / car
    # Algebra: SUM(R327..R334) telescopes to ``325 + cabin_depth + (25 + cladding)``
    # because R332 (= 325 - SUM(R327..R331)) cancels its own dependents. Same shape
    # for R346 (R338..R345). Result depends only on shaft depth + cabin depth +
    # cladding — not on the manufacturer choice — but we still emit both sides so
    # neither LD COMP_DIST cell is blank regardless of access type.
    if have_geom:
        dist = sd_mm - 325 - cd_mm_geom - car_wall_mm
        out["rear distance wall / car"] = _fmt_dim(dist)
        out["front distance wall / car"] = _fmt_dim(dist)

    # -------- R294 / R295 Offset door to center car (front / rear)
    # VT R294 is hard-coded 0; R295 mirrors it (= -R294 = 0). Always emit so the
    # CL_DIST LD cells aren't blank.
    out["offset door to center car front"] = "0"
    out["offset door to car center rear"] = "0"

    # -------- R300 distance cwt / wall = 50 mm (template default; used by R301/R335 algebra)
    cwt_wall_dist = 50
    out["distance cwt / wall"] = str(cwt_wall_dist)

    # -------- R349 / R351 / R352 Car / Left / Right rail (driven by load + CWT location)
    # R349 (Car rail) returns a rail name based on load capacity buckets — the LD
    # rule for it has F='n' so it is not exported, but we still publish the value
    # for the Schedules workbook (parameter "Car rail").
    load_kg_int = _to_int(load_kg_raw)
    if load_kg_int is not None:
        if load_kg_int <= 1350:
            out["car rail"] = "T90(75)"
        elif load_kg_int >= 2500:
            out["car rail"] = "T127(89)"
        else:
            out["car rail"] = "T125(82)"

    cwt_loc_norm = (cwt_loc or "").strip().lower()
    if cwt_loc_norm == "cwt-left":
        out["left rail"] = "9"
        out["right rail"] = "12"
        out["ctw rail name"] = "T75"
        out["ctw rail rid"] = "9"
    elif cwt_loc_norm == "cwt-right":
        out["left rail"] = "12"
        out["right rail"] = "9"
        out["ctw rail name"] = "T90"
        out["ctw rail rid"] = "12"

    # -------- R362 / R363 Door opening height = door height (M44)
    if door_h_used:
        out["front door opening height"] = _s(door_h_used)
        out["rear door opening height"] = _s(door_h_used)

    # -------- R369 / R374 Structural door opening width = M42 (door_width + 280)
    if dw_mm is not None:
        out["structural door opening width"] = str(dw_mm + 280)

    # NOTE: R368/R370 (Front entrance XLEFT/XRIGHT) depend on R301 ``cwt depth`` and
    # R306 ``right dist car`` which are computed at the bottom of this function (after
    # the wall_cwt lookup). The XLEFT/XRIGHT block therefore runs at the very end —
    # see the ``Front + Rear entrance centering`` section after the CWT block below.

    # -------- R377 CTW length: load-based bucket lookup
    if load_kg_int is not None:
        if load_kg_int <= 1000:
            out["ctw lenght"] = "1000"
        elif load_kg_int <= 2000:
            out["ctw lenght"] = "1500"
        elif load_kg_int <= 3500:
            out["ctw lenght"] = "2000"
        else:
            out["ctw lenght"] = "OUT OF RANGE"

    # -------- R381 Lop type: project default until UI captures it explicitly
    out["lop type"] = "Stadnard 150x300"  # VT spelling preserved (matches R384 IF arg)

    # -------- R383 / R388 LOP location (per LOP type and location dropdown)
    lop_loc_raw = _field(lift, "LOP type and location", "LOP type and locaion")
    lop_map = {
        "in lift door frame l": "138",
        "in lift door frame r": "146",
        "flush wall panel l": "140",
        "wall-mounted panel l": "140",
        "flush wall panel r": "148",
        "wall-mounted panel r": "148",
    }
    lop_loc_val = lop_map.get(lop_loc_raw.strip().lower(), "")
    if lop_loc_val:
        out["lop location"] = lop_loc_val

    # -------- R384 / R389 Panel type = 13 if LOP type == "Stadnard 150x300", else "non std."
    out["panel type"] = "13"

    # -------- R394 LIP location (per LIP type and location dropdown)
    lip_loc_raw = _field(lift, "LIP type and location")
    lip_map = {
        "door frame side vertical": "130",
        "panel above horizontal": "132",
    }
    if lip_loc_raw:
        out["location"] = lip_map.get(lip_loc_raw.strip().lower(), "non std.")

    # -------- R401..R418 Door-fixing rails (driven by R46 door fixation type, M46)
    door_fix = _field(lift, "door fixation type", "Door fixation type").strip().lower()
    rail_inserts = ("insert rail 40/22", "insert rail 50/30")

    if door_fix:
        # R401 / R411 ``turns on/ off rail`` — 1400105 for insert rails, else 1400106
        rail_turn = "1400105" if door_fix in rail_inserts else "1400106"
        out["turns on/ off rail"] = rail_turn
        out["rail on /off"] = rail_turn  # VT R411 label variant

        # R406 / R416 ``rail on/off`` — 21 for insert rails, else 9
        rail_onoff = "21" if door_fix in rail_inserts else "9"
        out["rail on/off"] = rail_onoff

        # R402 / R407 / R412 / R417 anchor / fixing — RID per fixation type
        anchor_map = {
            "insert rail 40/22": "1347",
            "insert rail 50/30": "3500003",
            "anchor bolts": "anchor bolts code",
            "steel structure": "steel structure code",
        }
        anchor_val = anchor_map.get(door_fix, "non std. Mounting")
        out["front door fixing bottom"] = anchor_val
        out["front door fixing top1"] = anchor_val
        out["rear door fixing bottom"] = anchor_val
        out["rear door fixing top"] = anchor_val

        # R397 Possible rail length: smallest catalogue length >= R396 perfect length.
        # R396 = M41 + 750 (2L/2R) or M41 + 900 (2C/4C/6C).
        if dw_mm is not None and front_door_type:
            if front_door_type in ("2L", "2R"):
                perfect_len = dw_mm + 750
            elif front_door_type in ("2C", "4C", "6C"):
                perfect_len = dw_mm + 900
            else:
                perfect_len = None
            if perfect_len is not None:
                if door_fix == "insert rail 40/22":
                    catalogue = (150, 200, 250, 300, 350, 400, 550, 800, 1050, 1300,
                                 1550, 1800, 2050, 2300, 2550, 3030, 6070)
                elif door_fix == "insert rail 50/30":
                    catalogue = (150, 200, 250, 300, 350, 400, 550, 800, 1050,
                                 3030, 6070)
                else:
                    catalogue = ()
                rail_len = next((x for x in catalogue if x >= perfect_len), None)
                rail_len_val = str(rail_len) if rail_len is not None else "no rail"
            else:
                rail_len_val = "no rail"
            out["front bottom rail length"] = rail_len_val
            out["front top rail lenght"] = rail_len_val
            out["length"] = rail_len_val

    # -------- R420 / R423 Brackets (driven by R53 shaft equipment fixation type)
    shaft_fix = _field(lift, "Shaft equipment fixation type").strip().lower()
    bracket_map = {
        "insert rail 40/22": "1",
        "insert rail 50/30": "493900023",
        "anchor bolts": "anchor bolts code",
        "steel structure": "steel structure code",
    }
    if shaft_fix:
        bracket_val = bracket_map.get(shaft_fix, "non std. Mounting")
        out["non ctw bracket"] = bracket_val
        out["ctw bracket"] = bracket_val

    # -------- R421 non-ctw bracket length = 550 mm (template default)
    out["non ctw bracket length"] = "550"

    # -------- R424 ctw bracket length = R377 + 500
    ctw_len = _to_int(out.get("ctw lenght", ""))
    if ctw_len is not None:
        out["ctw bracket lenth"] = str(ctw_len + 500)

    # ============================================================
    # Schedule-template aliases
    # ------------------------------------------------------------
    # The Schedules workbook (xxxxxxx_template_VT Schedules V3.0_de_en.xlsx) labels
    # several rows differently from the LD export sheet (e.g. "Shaft width proposal"
    # vs the LD/VT label "Shaft width suggested"). We expose aliases here so
    # ``_value_for_param`` finds them via the derived-fallback path without needing
    # to special-case every label in the resolver.
    _alias_pairs = (
        ("shaft width suggested", "shaft width proposal"),
        ("shaft depth suggested", "shaft depth proposal"),
        ("shaft head suggested", "shaft head proposal"),
        ("shaft pit suggested", "shaft pit proposal"),
    )
    for src, dst in _alias_pairs:
        if src in out and dst not in out:
            out[dst] = out[src]

    # UI-only fields that the LD ctx-dict lookup sees under different labels.
    # We mirror them under the schedule labels via compute_derived's fallback dict.
    ui_alias_pairs = (
        ("Machine room width suggested", "machine room width proposal"),
        ("Machine room depth suggested", "machine room depth proposal"),
        ("Machine room height suggested", "machine room height proposal"),
        ("Machine room width current planning", "machine room width current planning"),
        ("Machine room depth current planning", "machine room depth current planning"),
        ("Machine room height current planning", "machine room height current planning"),
        ("Shaft division type", "dividing type"),
        ("Shaft division width", "dividing width"),
        ("Lift maintenance panel type", "lift maintenance panel type"),
        ("Lift maintenance panel location", "lift maintenance panel location"),
        ("LIP type and location", "lip type"),
        ("LIP type and location", "lip location"),
    )
    for ui_key, sched_key in ui_alias_pairs:
        ui_val = _field(lift, ui_key)
        if ui_val and sched_key not in out:
            out[sched_key] = ui_val

    # -------- Open-through / adjacent access flags from the Access type dropdown
    access_norm = (access_type or "").strip().lower()
    out["open-through"] = "yes" if access_norm == "open through" else "no"
    out["adjacent access"] = "yes" if access_norm == "adjacent" else "no"

    # -------- Schematics & Occupancies: per-floor elevations
    # Schedule template has fixed labelled rows ("Ground floor (E0)",
    # "1st floor (E1)" … "2nd basement (E-2)"). Map each project floor to the
    # corresponding row by floor index — index 0 == E0, positive indices climb,
    # negative indices descend into basements.
    _ord_labels = {
        0: "ground floor (e0)",
        1: "1st floor (e1)",
        2: "2nd floor (e2)",
        3: "3rd floor (e3)",
        4: "4th floor (e4)",
        5: "5th floor (e5)",
        6: "6th floor (e6)",
        -1: "1st basement (e-1)",
        -2: "2nd basement (e-2)",
    }
    floors_root = user_inputs.get("Floors") or []
    if floors_root:
        first = floors_root[0] if isinstance(floors_root, list) else {}
        lift_floors_key = f"Lift {lift_index + 1}"
        floor_list = first.get(lift_floors_key, []) if isinstance(first, dict) else []
        for f in floor_list or []:
            if not isinstance(f, dict):
                continue
            try:
                idx = int(str(f.get("Floor", "")).strip())
            except (ValueError, TypeError):
                continue
            label = _ord_labels.get(idx)
            if not label:
                continue
            elev_raw = f.get("Elevation (m)", "")
            if elev_raw is None or str(elev_raw).strip() == "":
                continue
            out[label] = str(elev_raw).strip()

    # -------- R292 wall-distance CWT side
    wall_cwt = _lookup_wall_distance(
        _WALL_CWT_SIDE, cw_mm, dw_mm, door_type_used, accessible_yes, cladding_mm
    )
    if wall_cwt is not None:
        out["walldistance ctw side"] = str(wall_cwt)

    # -------- R293 wall-distance non-CWT side
    wall_noncwt = _lookup_wall_distance(
        _WALL_NON_CWT_SIDE, cw_mm, dw_mm, door_type_used, accessible_yes, cladding_mm
    )
    if wall_noncwt is not None:
        out["wall distance non-cwt side"] = str(wall_noncwt)

    # -------- R303 Left car wall / R305 Right car wall = 25 + cladding
    car_wall = int(round(25 + cladding_mm))
    out["left car wall"] = str(car_wall)
    out["right car wall"] = str(car_wall)

    # -------- R304 Car width (CW) = cabin width
    if cw_mm is not None:
        out["car width"] = str(cw_mm)

    # -------- R301 Cwt depth = (R292 − R300 − R303) / 2  (R300 default 50 per template)
    cwt_wall_dist_default = 50  # Excel constant in template
    if wall_cwt is not None:
        cwt_depth = (wall_cwt - cwt_wall_dist_default - car_wall) / 2.0
        out["cwt depth"] = _fmt_dim(cwt_depth)
        # -------- R302 LEFT distance FROM CAR / R306 RIGHT DIST CAR
        loc_lower = cwt_loc.strip().lower()
        if loc_lower == "cwt-left":
            out["left distance from car"] = _fmt_dim(cwt_depth)
            if wall_noncwt is not None:
                out["right dist car"] = _fmt_dim(wall_noncwt - car_wall)
        elif loc_lower == "cwt-right":
            out["right dist car"] = _fmt_dim(cwt_depth)
            if wall_noncwt is not None:
                out["left distance from car"] = _fmt_dim(wall_noncwt - car_wall)

    # -------- R368 / R370 / R373 / R375 Front + Rear entrance centering (XLEFT / XRIGHT)
    # VT formula:
    #   R369 = M42 (struct door opening width)
    #   R370 (front XRIGHT):
    #     CWT-Left:  (R306 + R305 + R304/2) - M42/2 - R294
    #     CWT-Right: (R300 + R301 + R306 + R305 + R304/2) - M42/2 + R294
    #   R368 (front XLEFT) = M54 - R369 - R370
    #   R373 (rear XLEFT) = R370   R375 (rear XRIGHT) = R368
    sw_mm_xc = _to_int(out.get("shaft width suggested", ""))
    cw_mm_geom = _to_int(cabin_w_used)
    if dw_mm is not None and cw_mm_geom is not None and sw_mm_xc is not None:
        struct_door_w = dw_mm + 280
        cwt_depth_val = _to_float(out.get("cwt depth", ""))
        right_dist_val = _to_float(out.get("right dist car", ""))
        offset = 0  # R294
        loc_xc = cwt_loc.strip().lower()
        right_side_front: Optional[float] = None
        if loc_xc == "cwt-left" and right_dist_val is not None:
            right_side_front = (
                right_dist_val + car_wall + cw_mm_geom / 2.0
            ) - struct_door_w / 2.0 - offset
        elif (
            loc_xc == "cwt-right"
            and right_dist_val is not None
            and cwt_depth_val is not None
        ):
            right_side_front = (
                cwt_wall_dist_default
                + cwt_depth_val
                + right_dist_val
                + car_wall
                + cw_mm_geom / 2.0
            ) - struct_door_w / 2.0 + offset

        if right_side_front is not None:
            left_side_front = sw_mm_xc - struct_door_w - right_side_front
            out["right side of the wall"] = _fmt_dim(right_side_front)
            out["left side of the wall"] = _fmt_dim(left_side_front)

    return out
