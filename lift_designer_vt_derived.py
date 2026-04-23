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


__all__ = ["compute_derived"]


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

def compute_derived(user_inputs: Mapping[str, Any], lift_index: int) -> Dict[str, str]:
    """
    Compute VT-formula values for lift ``lift_index``; keys are normalized parameter labels.

    Only returns entries that can be computed from the available UI inputs. Missing entries
    mean "no override" — the LD export should keep the UI value (even if empty).
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

    # -------- R279/R281 Shaft doors, R287/R289 Cabin doors
    # These VT rows use an XLOOKUP in the 'selection' sheet to return a LiftDesigner
    # product ID (e.g. 1400086) based on door component maker ("Common component" /
    # "Meiller"), door type code, and door width. The door component maker is not yet
    # captured in the UI, so we leave the cells empty until that input is added and
    # the selection-sheet tables are ported. Writing the door-type code here would be
    # wrong (the VT formula returns an LD product ID, not the code).

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

    return out
