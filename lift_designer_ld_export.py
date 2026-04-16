"""
Lift Designer → LD import workbook (non-UI).

Export rules come only from ``VT standard configurations_V00.xlsx`` sheet
``VT Standard configs`` column **F** (LD export) when the cell contains an explicit
LD variable path (``Shaft0…``, ``FLL…``, ``L_Projects…``, etc.). Rows marked
``no`` or ``yes, info`` are not exported.

Per **lift index** ``i`` (0 = Lift 1, 1 = Lift 2, …): ``Shaft0`` in paths becomes
``Shaft{i}``. For **Connected load**, **Rated current**, and **Heat dissipation motor**,
``L_Projects.PROJ_USER_*`` is remapped: Lift 1 → 0, 2, 3; Lift 2+ → consecutive triples
starting at ``3*i + 1`` (e.g. Lift 2: 4–6, Lift 3: 7–9, Lift 4: 10–12).

Workbook layout (``SyncWithLD``): row **1** = titles in **A–F** and **Mode declaration** in **G1**;
**G2–G4** hold the three mode lines on the **same** rows as the first content in **A–F** (Shaft0 data may start on row **2**).
Default output file: ``LD data import test.xlsx``.

Use :func:`write_ld_workbook_multi` with one row list per lift to produce a **single** workbook:
preamble once, then **Shaft 1**, **Shaft 2**, … section rows before each additional lift’s block.
"""
from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

from gui.project_lift_schema import merged_lift_at

__all__ = [
    "LDExportRow",
    "VTExportRule",
    "load_vt_export_rules",
    "build_ld_rows_from_user_inputs",
    "build_ld_rows_per_lift",
    "matrix_for_ld_workbook",
    "write_ld_workbook",
    "write_ld_workbook_multi",
    "write_ld_csv",
    "export_ld_data_import_test",
    "default_vt_workbook_path",
    "default_ld_empty_template_path",
    "default_ld_example_path",
    "remap_varname_for_lift",
]

Number = Union[int, float]


@dataclass(frozen=True)
class LDExportRow:
    varname: str
    value: str = ""
    description: str = ""


@dataclass
class VTExportRule:
    """One logical rule from the VT sheet (row order preserved)."""

    kind: str  # "static" | "floors_z" | "floors_desc"
    varnames: List[str] = field(default_factory=list)
    param_label: str = ""
    vt_row: int = 0


def default_vt_workbook_path() -> str:
    return os.path.join(os.path.dirname(__file__), "VT standard configurations_V00.xlsx")


def default_ld_empty_template_path() -> str:
    return os.path.join(os.path.dirname(__file__), "LD Export Empty file.xlsx")


def default_ld_example_path() -> str:
    return os.path.join(os.path.dirname(__file__), "LD example data import.xlsx")


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v).strip()


def _norm_param(s: str) -> str:
    return " ".join(str(s).lower().split())


def _is_no_export(cell_val: Any) -> bool:
    if cell_val is None:
        return True
    t = str(cell_val).strip().lower()
    return t in ("", "no", "n", "none")


def _parse_ld_path_lines(cell_val: Any) -> List[str]:
    """Split column F; keep lines that look like LD property paths."""
    if cell_val is None:
        return []
    raw = str(cell_val).strip()
    if not raw or raw in ("-", "?", "yes, info", "yes,info"):
        return []
    out: List[str] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln or ln == "?":
            continue
        if _is_no_export(ln):
            continue
        if ln.lower() in ("yes, info", "yes,info"):
            continue
        out.append(ln)
    return out


def _looks_like_ld_path(s: str) -> bool:
    """True if ``s`` is an explicit LD path from VT (not ``no`` / ``yes, info`` / ``-``)."""
    s = s.strip()
    if not s:
        return False
    low = s.lower()
    if low in ("no", "n") or low.startswith("no,"):
        return False
    if low in ("yes, info", "yes,info", "-", "?"):
        return False
    return bool(
        re.match(r"^Shaft0(\.|$)", s)
        or s.startswith("FLL.")
        or s.startswith("L_")
        or s.startswith("Shaft.")
    )


def _proj_user_triple_indices(lift_index: int) -> Tuple[int, int, int]:
    """
    ``L_Projects`` suffixes for Connected load, Rated current, Heat dissipation motor.

    Lift 1 (index 0): 0, 2, 3 — Lift k (index i≥1): ``3*i+1``, ``3*i+2``, ``3*i+3``
    (Lift 2: 4–6, Lift 3: 7–9, Lift 4: 10–12, …).
    """
    if lift_index <= 0:
        return (0, 2, 3)
    base = 3 * lift_index + 1
    return (base, base + 1, base + 2)


def remap_varname_for_lift(varname: str, param_label: str, lift_index: int) -> str:
    """
    VT paths use ``Shaft0…``; replace with ``Shaft{n}`` where ``n`` == ``lift_index``.
    Remap ``L_Projects.PROJ_USER_*`` for the three electrical parameters per lift.
    """
    vn = varname.strip()
    norm = _norm_param(param_label)

    if vn.startswith("L_Projects.PROJ_USER_"):
        ic, ir, ih = _proj_user_triple_indices(lift_index)
        if norm == "connected load":
            return f"L_Projects.PROJ_USER_{ic}"
        if norm == "rated current":
            return f"L_Projects.PROJ_USER_{ir}"
        if norm == "heat dissipation motor":
            return f"L_Projects.PROJ_USER_{ih}"
        return vn

    if lift_index == 0:
        return vn
    # Shaft0 → Shaft{lift_index} (VT template is always Shaft0 for lift 1)
    return re.sub(r"\bShaft0\b", f"Shaft{lift_index}", vn)


def load_vt_export_rules(
    path_vt: Optional[str] = None,
) -> List[VTExportRule]:
    """
    Scan ``VT Standard configs`` column A (parameter) and F (LD export).
    """
    path_vt = path_vt or default_vt_workbook_path()

    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise ImportError("pip install openpyxl") from e

    wb = load_workbook(path_vt, data_only=True)
    if "VT Standard configs" not in wb.sheetnames:
        wb.close()
        return []
    ws = wb["VT Standard configs"]
    rules: List[VTExportRule] = []
    seen_z = False
    seen_desc = False

    for r in range(3, ws.max_row + 1):
        param = ws.cell(r, 1).value
        fcell = ws.cell(r, 6).value
        if not param and not fcell:
            continue
        plab = _s(param)
        if not plab:
            continue
        if fcell is None or str(fcell).strip() == "":
            continue
        fs = str(fcell).strip()
        if fs.lower() in ("yes, info", "yes,info"):
            continue
        if _is_no_export(fs):
            continue
        if fs == "-":
            continue
        lines = _parse_ld_path_lines(fs)
        if not lines:
            continue
        # Multiline: split LD paths vs noise
        paths = [ln.strip() for ln in lines if _looks_like_ld_path(ln.strip())]
        if not paths:
            continue
        if any(re.match(r"^FLL\.Level\d+\.Z_POT$", x) for x in paths):
            if not seen_z:
                rules.append(VTExportRule("floors_z", [], plab, r))
                seen_z = True
            continue
        if any(re.match(r"^FLL\.Level\d+\.DESC$", x) for x in paths):
            if not seen_desc:
                rules.append(VTExportRule("floors_desc", [], plab, r))
                seen_desc = True
            continue
        rules.append(VTExportRule("static", paths, plab, r))

    wb.close()
    return rules


@dataclass
class _ExportCtx:
    user_inputs: Mapping[str, Any]
    lift_index: int
    lift: Dict[str, Any]
    forces: Dict[str, Any]
    drive: Dict[str, Any]
    compliance: Dict[str, Any]
    emergency: Dict[str, Any]
    cost: Dict[str, Any]


def _lift(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    return merged_lift_at(ui, i) if isinstance(ui, dict) else {}


def _forces(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("Forces") or []
    if 0 <= i < len(rows) and isinstance(rows[i], dict):
        return rows[i]
    return {}


def _drive(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("LiftDrive") or []
    if 0 <= i < len(rows) and isinstance(rows[i], dict):
        return rows[i]
    return {}


def _compliance(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("Compliance") or []
    if 0 <= i < len(rows) and isinstance(rows[i], dict):
        return rows[i]
    return {}


def _emergency(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("Emergency") or []
    if 0 <= i < len(rows) and isinstance(rows[i], dict):
        return rows[i]
    return {}


def _cost(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("Cost") or []
    if 0 <= i < len(rows) and isinstance(rows[i], dict):
        return rows[i]
    return {}


def _floors_list(ui: Mapping[str, Any], i: int) -> List[MutableMapping[str, Any]]:
    floors = ui.get("Floors") or []
    if i >= len(floors) or not isinstance(floors[i], dict):
        return []
    block = floors[i]
    key = f"Lift {i + 1}"
    raw = block.get(key) if key in block else next(iter(block.values()), [])
    return list(raw) if isinstance(raw, list) else []


def _get_lift_field(lift: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = lift.get(k)
        if v is not None and str(v).strip() != "":
            return _s(v)
    return ""


# Applicable codes page: checkbox row labels — export the label only when checked.
_LD_COMPLIANCE_CHECKBOX_LABELS: Tuple[str, ...] = (
    "EN81-28 emergency call",
    "EN81-70 Accessibility",
    "DIN EN17210 / 18040-1 Accessibility",
    "EN81-72 Firefighter elevator",
    "EN81-73 Fire emergency return",
    "EN81-58 Fire rated landing doors",
)


def _compliance_checkbox_selected(v: Any) -> bool:
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("yes", "true", "1"):
        return True
    return False


def _compliance_summary(ui: Mapping[str, Any], i: int) -> str:
    """
    Text for ``L_StandardTab.STD_DESC`` / “Applied codes”: only entries the user effectively
    selected (checked checkboxes; combos/fields omit neutral defaults like category ``0`` or ``no``).
    """
    comp = ui.get("Compliance") or []
    if i >= len(comp) or not isinstance(comp[i], dict):
        return ""
    d = comp[i]
    parts: List[str] = []

    for label in _LD_COMPLIANCE_CHECKBOX_LABELS:
        if label not in d:
            continue
        if _compliance_checkbox_selected(d[label]):
            parts.append(label)

    v = d.get("EN81-71 Vandalism category")
    if v is not None and str(v).strip() not in ("", "0"):
        parts.append(f"EN81-71 Vandalism category={_s(v)}")

    v = d.get("EN81-76 Emergency Evacuation type")
    if isinstance(v, str) and v.strip() and v.strip().lower() != "no":
        parts.append(f"EN81-76 Emergency Evacuation type={v.strip()}")

    v = d.get("EN81-76 Evacuation functions")
    if v is not None and str(v).strip():
        parts.append(f"EN81-76 Evacuation functions={_s(v)}")

    v = d.get("EN81-77 Seismic category")
    if v is not None and str(v).strip() not in ("", "0"):
        parts.append(f"EN81-77 Seismic category={_s(v)}")

    v = d.get("Green building certification compliance")
    if v is not None and str(v).strip():
        parts.append(f"Green building certification compliance={_s(v)}")

    v = d.get("EN81-58 Fire rating class")
    if isinstance(v, bool):
        if v:
            parts.append("EN81-58 Fire rating class")
    elif isinstance(v, str) and v.strip():
        parts.append(f"EN81-58 Fire rating class={v.strip()}")

    return "; ".join(parts)


def _emergency_summary(em: Dict[str, Any]) -> str:
    parts: List[str] = []
    for k, v in em.items():
        if isinstance(v, str) and v.strip():
            parts.append(f"{k}={v}")
    return "; ".join(parts)


# --- Parameter label (VT column A, normalized) → value resolver ---

def _val_system_name(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "System Type") or _s(ctx.user_inputs.get("FileName", ""))


def _val_configuration_short(ctx: _ExportCtx) -> str:
    return _s(ctx.user_inputs.get("FileName", ""))


def _val_counterweight(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Counterweight location")


def _val_load(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Load capacity", "Load capacity (kg)")


def _val_persons(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Permissible number of persons", "Permissible number of persons (Pers.)")


def _val_speed(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Speed", "Speed (m/s)")


def _val_num_floors_fll(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Number of floors", "Number of floors (Stck.)")


def _val_stops(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Stops", "Stops (Stck.)")


def _val_cw(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Cabin width", "Cabin width (mm)")


def _val_cd(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Cabin depth", "Cabin depth (mm)")


def _val_height(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Structural cabin height", "Structural cabin height (mm)")


def _val_door_open_b(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Door structural opening width", "Door structural opening width (mm)")


def _val_head(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Shaft head suggested", "Shaft head suggested (mm)")


def _val_pit(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Shaft pit suggested", "Shaft pit suggested (mm)")


def _val_connected(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.drive, "Connected load", "Connected load (kVA)")


def _val_rated_i(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.drive, "Rated current", "Rated current (A)")


def _val_heat(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.drive, "Heat dissipation motor", "Heat dissipation motor (kJ)")


def _val_clad(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Cladding thickness each wall", "Cladding thickness each wall (mm)")


def _val_force_f12(ctx: _ExportCtx) -> str:
    return _get_lift_field(
        ctx.forces,
        "Force F1, F2 elevator rail segment",
        "Force F1, F2 elevator rail segment (kN)",
    )


def _val_force_f3(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force F3, each buffer", "Force F3, each buffer (kN)")


def _val_force_f4(ctx: _ExportCtx) -> str:
    return _get_lift_field(
        ctx.forces,
        "Force F4, per counterweight rail segment",
        "Force F4, per counterweight rail segment (kN)",
    )


def _val_force_f5(ctx: _ExportCtx) -> str:
    return _get_lift_field(
        ctx.forces,
        "Force F5, per counterweight buffer",
        "Force F5, per counterweight buffer (kN)",
    )


def _val_force_f6(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force F6, static shaft door", "Force F6, static shaft door (kN)")


def _val_force_f7(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force F7, static counterweight", "Force F7, static counterweight (kN)")


def _val_force_f8(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force F8, static cabin", "Force F8, static cabin (kN)")


def _val_force_fx_car(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force Fx, cabin rail", "Force Fx, cabin rail (kN)")


def _val_force_fy_car(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force Fy, cabin rail", "Force Fy, cabin rail (kN)")


def _val_force_fx_cwt(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force Fx, counterweight rail", "Force Fx, counterweight rail (kN)")


def _val_force_fy_cwt(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.forces, "Force Fy, counterweight rail", "Force Fy, counterweight rail (kN)")


def _val_std_desc(ctx: _ExportCtx) -> str:
    return _compliance_summary(ctx.user_inputs, ctx.lift_index)


def _val_lop(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "LOP type and location", "LOP type and locaion")


def _val_lip(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "LIP type and location")


def _val_door_h(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Door height", "Door height (mm)")


def _val_door_type(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "door type")


def _val_shaft_width(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Shaft width suggested", "Shaft width suggested (mm)")


def _val_shaft_depth(ctx: _ExportCtx) -> str:
    return _get_lift_field(ctx.lift, "Shaft depth suggested", "Shaft depth suggested (mm)")


PARAM_RESOLVERS: Dict[str, Callable[[_ExportCtx], str]] = {
    "configuration short name": _val_configuration_short,
    "system name": _val_system_name,
    "load capacity": _val_load,
    "permissible number of persons": _val_persons,
    "speed": _val_speed,
    "number of floors": _val_num_floors_fll,
    "stops": _val_stops,
    "cabin width (clear)": _val_cw,
    "cabin depth (clear)": _val_cd,
    "structural cabin height": _val_height,
    "door structural opening width": _val_door_open_b,
    "shaft head suggested": _val_head,
    "shaft pit suggested": _val_pit,
    "connected load": _val_connected,
    "rated current": _val_rated_i,
    "heat dissipation motor": _val_heat,
    "energy recovery": lambda c: _get_lift_field(c.drive, "Energy recovery", "Energy recovery (y/n)"),
    "diversity factor": lambda c: _get_lift_field(c.drive, "Diversity factor", "Diversity factor (-)"),
    "energy consumption": lambda c: _get_lift_field(c.drive, "Energy consumption", "Energy consumption (kWh)"),
    "force f1, f2 elevator rail segment": _val_force_f12,
    "force f3, each buffer": _val_force_f3,
    "force f4, per counterweight rail segment": _val_force_f4,
    "force f5, per counterweight buffer": _val_force_f5,
    "force f6, static shaft door": _val_force_f6,
    "force f7, static counterweight": _val_force_f7,
    "force f8, static cabin": _val_force_f8,
    "force fx, cabin rail": _val_force_fx_car,
    "force fy, cabint rail": _val_force_fy_car,
    "force fy, cabin rail": _val_force_fy_car,
    "force fx, counterweight rail": _val_force_fx_cwt,
    "force fy, counterweight rail": _val_force_fy_cwt,
    "applied codes": _val_std_desc,
    "cladding thickness each wall": _val_clad,
    "lop type and location": _val_lop,
    "lip type and location": _val_lip,
    "door width": lambda c: _get_lift_field(c.lift, "Door width", "Door width (mm)"),
    "door height": _val_door_h,
    "door type": _val_door_type,
    "shaft width suggested": _val_shaft_width,
    "shaft depth suggested": _val_shaft_depth,
    "counterweight location": _val_counterweight,
}


def _value_for_param(param_label: str, ctx: _ExportCtx) -> str:
    key = _norm_param(param_label)
    fn = PARAM_RESOLVERS.get(key)
    if fn:
        return fn(ctx)
    # Special: L_StandardTab.STD_DESC description "Applied codes"
    if "applied codes" in key:
        return _val_std_desc(ctx)
    # Fallback: exact key on merged lift
    for dk, dv in ctx.lift.items():
        if isinstance(dk, str) and _norm_param(dk) == key:
            return _s(dv)
    return ""


def _coerce_cell_value(val: str) -> Union[str, Number]:
    if val is None or val == "":
        return ""
    s = str(val).strip()
    if re.fullmatch(r"-?\d+", s):
        try:
            return int(s)
        except ValueError:
            return s
    if re.fullmatch(r"-?\d+[\.,]\d+", s):
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return s
    return val


def _rows_for_floors_z(ctx: _ExportCtx) -> List[LDExportRow]:
    out: List[LDExportRow] = []
    floors = _floors_list(ctx.user_inputs, ctx.lift_index)
    z_cum = 0.0
    for idx, floor in enumerate(floors):
        try:
            h_mm = float(str(floor.get("Height (m)", "0")).replace(",", ".")) * 1000.0
        except (ValueError, TypeError, OverflowError):
            h_mm = 0.0
        fname = _s(floor.get("Floor Name", floor.get("Floor", "")))
        label = fname if fname else f"Level {idx}"
        out.append(
            LDExportRow(
                f"FLL.Level{idx}.Z_POT",
                str(int(round(z_cum))),
                label,
            )
        )
        z_cum += h_mm
    return out


def _rows_for_floors_desc(ctx: _ExportCtx) -> List[LDExportRow]:
    out: List[LDExportRow] = []
    floors = _floors_list(ctx.user_inputs, ctx.lift_index)
    for idx, floor in enumerate(floors):
        fn = _s(floor.get("Floor Name", ""))
        fl = _s(floor.get("Floor", ""))
        out.append(LDExportRow(f"FLL.Level{idx}.DESC", fn, fl or fn))
    return out


def build_ld_rows_from_user_inputs(
    user_inputs: Mapping[str, Any],
    lift_index: int = 0,
    vt_path: Optional[str] = None,
) -> List[LDExportRow]:
    """
    Build export rows using ``VT standard configurations`` LD export column.
    """
    ctx = _ExportCtx(
        user_inputs=user_inputs,
        lift_index=lift_index,
        lift=_lift(user_inputs, lift_index),
        forces=_forces(user_inputs, lift_index),
        drive=_drive(user_inputs, lift_index),
        compliance=_compliance(user_inputs, lift_index),
        emergency=_emergency(user_inputs, lift_index),
        cost=_cost(user_inputs, lift_index),
    )
    rules = load_vt_export_rules(vt_path)
    rows: List[LDExportRow] = []

    for rule in rules:
        if rule.kind == "floors_z":
            rows.extend(_rows_for_floors_z(ctx))
            continue
        if rule.kind == "floors_desc":
            rows.extend(_rows_for_floors_desc(ctx))
            continue

        val = _value_for_param(rule.param_label, ctx)
        for vn in rule.varnames:
            tv = remap_varname_for_lift(vn, rule.param_label, ctx.lift_index)
            rows.append(LDExportRow(tv, val, rule.param_label))

    return rows


def _section_row_f(title: str) -> List[Any]:
    """Empty row with section title in column F only (bold applied when writing xlsx)."""
    return [None, None, None, None, None, title, None]


def _is_mechanical_loading_var(varname: str) -> bool:
    vn = varname or ""
    return bool(
        vn
        and (
            "Force0.F" in vn
            or "Buffer0.Force" in vn
            or "UBolt.Force" in vn
        )
    )


def _ld_workbook_preamble() -> List[List[Any]]:
    """Row 1 only: **A–F** titles and **G1** = *Mode declaration* (see :func:`_apply_ld_mode_legend_to_rows_g234`)."""
    c, d = "DTV_MODE", "SYNC_MODE"
    return [
        ["DTV_VARNAME", "DTV_VALUE", c, d, None, None, "Mode declaration"],
    ]


_LD_MODE_LEGEND_G234: Tuple[str, str, str] = (
    "1: Read property from Liftdesigner",
    "2: Write back to Liftdesigner",
    "3: Read from LD & write to LD",
)


def _apply_ld_mode_legend_to_rows_g234(matrix: List[List[Any]]) -> None:
    """Set **G** on Excel rows 2–4 (0-based indices 1–3) to the three mode lines; may overlap A–F on those rows."""
    for i in range(3):
        r = 1 + i
        if r >= len(matrix):
            break
        row = matrix[r]
        while len(row) < 7:
            row.append(None)
        row[6] = _LD_MODE_LEGEND_G234[i]


def matrix_for_ld_workbook(rows: Sequence[LDExportRow]) -> Tuple[List[List[Any]], List[int]]:
    """
    Build a 7-column grid like the reference ``LD example data import.xlsx``:

    - Row **1**: titles in **A–F**, **G1** = *Mode declaration*; **G2–G4** = mode lines on rows **2–4** (with A–F on those rows).
    - Section breaks: empty row with **bold** title in column **F** only.
    - Parameter rows: A–D values, description in **F**, **G** empty.

    Returns ``(matrix, section_header_row_indices)`` (1-based row numbers for bold F cells).
    """
    matrix: List[List[Any]] = list(_ld_workbook_preamble())
    section_rows_1based: List[int] = []
    seen_elec = False
    seen_mech = False
    seen_codes = False
    seen_z = False
    seen_desc = False

    for r in rows:
        if not str(r.varname).strip() and not str(r.value).strip():
            continue
        vn = str(r.varname).strip()

        if vn.startswith("L_Projects.") and not seen_elec:
            matrix.append(_section_row_f("Electrical & HVAC"))
            section_rows_1based.append(len(matrix))
            seen_elec = True

        if _is_mechanical_loading_var(vn) and not seen_mech:
            matrix.append(_section_row_f("Mechanical Loading"))
            section_rows_1based.append(len(matrix))
            seen_mech = True

        if vn == "L_StandardTab.STD_DESC" and not seen_codes:
            matrix.append(_section_row_f("Applicable codes"))
            section_rows_1based.append(len(matrix))
            matrix.append(_section_row_f("Lift Designer parameters"))
            section_rows_1based.append(len(matrix))
            seen_codes = True

        if ".Z_POT" in vn and not seen_z:
            matrix.append(_section_row_f("Level name"))
            section_rows_1based.append(len(matrix))
            seen_z = True

        if ".DESC" in vn and not seen_desc:
            matrix.append(_section_row_f("Level name"))
            section_rows_1based.append(len(matrix))
            seen_desc = True

        matrix.append(
            [
                r.varname,
                _coerce_cell_value(r.value) if isinstance(r.value, str) else r.value,
                0,
                2,
                None,
                r.description or None,
                None,
            ]
        )

    _apply_ld_mode_legend_to_rows_g234(matrix)
    return matrix, section_rows_1based


def build_ld_rows_per_lift(
    user_inputs: Mapping[str, Any],
    num_lifts: int,
    vt_path: Optional[str] = None,
) -> List[List[LDExportRow]]:
    """Return ``num_lifts`` row lists: index ``i`` is ``build_ld_rows_from_user_inputs(..., lift_index=i)``."""
    n = max(0, int(num_lifts))
    return [build_ld_rows_from_user_inputs(user_inputs, lift_index=i, vt_path=vt_path) for i in range(n)]


def matrix_for_ld_workbook_multi(
    rows_by_lift: Sequence[Sequence[LDExportRow]],
) -> Tuple[List[List[Any]], List[int]]:
    """
    Single sheet: preamble once, then each lift's block. Before lift index ``i`` (``i >= 1``),
    insert a bold **Shaft *i*** row in column **F** (same style as other section titles).

    Each lift uses a fresh copy of the internal section headers (Electrical & HVAC, …).
    """
    matrix: List[List[Any]] = list(_ld_workbook_preamble())
    section_row_nums: List[int] = []
    for i, rows in enumerate(rows_by_lift):
        if i > 0:
            matrix.append(_section_row_f(f"Shaft {i}"))
            section_row_nums.append(len(matrix))
        sub_m, sub_sec = matrix_for_ld_workbook(list(rows))
        body = sub_m[1:]
        offset = len(matrix)
        matrix.extend(body)
        for s in sub_sec:
            if s > 1:
                section_row_nums.append(offset + (s - 1))
    return matrix, section_row_nums


def _matrix_for_workbook(rows: Sequence[LDExportRow]) -> List[List[Any]]:
    """Backward-compatible wrapper; section styling is applied in :func:`write_ld_workbook`."""
    m, _ = matrix_for_ld_workbook(rows)
    return m


def _rows_to_matrix_csv(rows: Sequence[LDExportRow]) -> List[List[str]]:
    """Legacy CSV (no preamble legend in A)."""
    out: List[List[str]] = [
        ["DTV_VARNAME", "DTV_VALUE", "DTV_MODE", "SYNC_MODE", "", "", ""],
    ]
    for r in rows:
        if not str(r.varname).strip() and not str(r.value).strip():
            continue
        out.append([r.varname, _s(r.value), "0", "2", "", r.description, ""])
    return out


def write_ld_csv(path: str, rows: Sequence[LDExportRow]) -> None:
    matrix = _rows_to_matrix_csv(rows)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for line in matrix:
            w.writerow(line)


def _write_ld_matrix_to_path(
    path: str,
    matrix: List[List[Any]],
    section_row_nums: Sequence[int],
    sheet_title: str = "SyncWithLD",
) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        raise ImportError("pip install openpyxl") from e
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    font_header = Font(bold=True)
    font_section = Font(bold=True)
    align_left = Alignment(horizontal="left", vertical="center")
    align_center = Alignment(horizontal="center", vertical="center")

    def _alignment_for_column(c_idx: int) -> Alignment:
        # A, F, G: left; B, C, D: center; E: left (unused spacer)
        if c_idx in (1, 5, 6, 7):
            return align_left
        return align_center

    for r_idx, line in enumerate(matrix, start=1):
        for c_idx, cell in enumerate(line, start=1):
            if c_idx > 7:
                continue
            cl = ws.cell(row=r_idx, column=c_idx, value=cell)
            cl.alignment = _alignment_for_column(c_idx)
            if r_idx == 1 and cell is not None:
                cl.font = font_header
            if r_idx in section_row_nums and c_idx == 6 and cell is not None:
                cl.font = font_section

    for col in range(1, 8):
        letter = get_column_letter(col)
        max_len = 0
        for r in range(1, ws.max_row + 1):
            v = ws.cell(row=r, column=col).value
            if v is not None:
                max_len = max(max_len, len(str(v)))
        ws.column_dimensions[letter].width = min(max(max_len + 2.5, 12), 85)

    wb.save(path)


def write_ld_workbook_multi(
    path: str,
    rows_by_lift: Sequence[Sequence[LDExportRow]],
    sheet_title: str = "SyncWithLD",
) -> None:
    """Write one ``SyncWithLD`` sheet with all lifts stacked; **Shaft *n*** separates lift blocks (``n >= 1``)."""
    matrix, section_row_nums = matrix_for_ld_workbook_multi(rows_by_lift)
    _write_ld_matrix_to_path(path, matrix, section_row_nums, sheet_title=sheet_title)


def write_ld_workbook(
    path: str,
    rows: Sequence[LDExportRow],
    sheet_title: str = "SyncWithLD",
) -> None:
    write_ld_workbook_multi(path, [rows], sheet_title=sheet_title)


def export_ld_data_import_test(
    user_inputs: Mapping[str, Any],
    lift_index: int = 0,
    output_path: Optional[str] = None,
    vt_path: Optional[str] = None,
) -> str:
    """
    Write ``LD data import test.xlsx`` next to this module (or ``output_path``).
    Returns the path written.
    """
    out = output_path or os.path.join(os.path.dirname(__file__), "LD data import test.xlsx")
    rows = build_ld_rows_from_user_inputs(
        user_inputs,
        lift_index=lift_index,
        vt_path=vt_path,
    )
    write_ld_workbook(out, rows)
    return out


if __name__ == "__main__":
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Export project data to LD data import Excel (SyncWithLD).")
    p.add_argument(
        "project_json",
        nargs="?",
        default=None,
        help="Path to a LiftDesign project .json file. If omitted, a minimal demo dict is used.",
    )
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output .xlsx path (default: LD data import test.xlsx next to this script).",
    )
    p.add_argument(
        "-l",
        "--lift",
        type=int,
        default=0,
        help="Lift index (0-based). Ignored if --all-lifts. Default: 0.",
    )
    p.add_argument(
        "--all-lifts",
        action="store_true",
        help="Write one workbook with every lift stacked (Shaft 1, Shaft 2, … section rows between blocks).",
    )
    args = p.parse_args()

    if args.project_json:
        try:
            from gui.project_json import load_project_json
        except ImportError:
            print("Import error: run from the project root so the gui package is found.", file=sys.stderr)
            raise SystemExit(1) from None
        data = load_project_json(args.project_json)
    else:
        if args.all_lifts:
            data = {
                "FileName": "demo",
                "BuildingSystems": [{}, {}],
                "GeneralSpecification": [{}, {}],
                "LayoutInformation": [{}, {}],
                "LiftDrive": [{}, {}],
                "Forces": [{}, {}],
                "Compliance": [{}, {}],
                "Floors": [{"Lift 1": []}, {"Lift 2": []}],
            }
        else:
            data = {
                "FileName": "demo",
                "BuildingSystems": [{}],
                "GeneralSpecification": [{}],
                "LayoutInformation": [{}],
                "LiftDrive": [{}],
                "Forces": [{}],
                "Compliance": [{}],
                "Floors": [{"Lift 1": []}],
            }

    out = args.output or os.path.join(os.path.dirname(__file__), "LD data import test.xlsx")
    if args.all_lifts:
        n = len(data.get("BuildingSystems") or [])
        rows_by_lift = build_ld_rows_per_lift(data, n)
        write_ld_workbook_multi(out, rows_by_lift)
        path = out
    else:
        path = export_ld_data_import_test(
            data,
            lift_index=args.lift,
            output_path=args.output,
        )
    print(path)
