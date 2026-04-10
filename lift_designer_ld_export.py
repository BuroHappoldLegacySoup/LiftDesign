"""
Lift Designer → LD import sheet (non-UI).

Columns match ``LD example data import(SyncWithLD).csv``:
A ``DTV_VARNAME``, B ``DTV_VALUE``, C ``DTV_MODE`` (=0), D ``SYNC_MODE`` (=2), E blank, F description.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence

from gui.project_lift_schema import merged_lift_at

__all__ = [
    "LDExportRow",
    "build_ld_rows_from_user_inputs",
    "write_ld_workbook",
    "write_ld_csv",
]


@dataclass(frozen=True)
class LDExportRow:
    varname: str
    value: str = ""
    description: str = ""


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v).strip()


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


def _cost(ui: Mapping[str, Any], i: int) -> Dict[str, Any]:
    rows = ui.get("Cost") or []
    if 0 <= i < len(rows) and isinstance(rows[i], dict):
        return rows[i]
    return {}


def _compliance_summary(ui: Mapping[str, Any], i: int) -> str:
    comp = ui.get("Compliance") or []
    if i >= len(comp) or not isinstance(comp[i], dict):
        return ""
    parts: List[str] = []
    for k, v in comp[i].items():
        if v is True or (isinstance(v, str) and v.lower() in ("yes", "true", "1")):
            parts.append(k)
        elif isinstance(v, str) and v.strip():
            parts.append(f"{k}={v}")
    return "; ".join(parts)


def _floors(ui: Mapping[str, Any], i: int) -> List[MutableMapping[str, Any]]:
    floors = ui.get("Floors") or []
    if i >= len(floors) or not isinstance(floors[i], dict):
        return []
    block = floors[i]
    key = f"Lift {i + 1}"
    raw = block.get(key) if key in block else next(iter(block.values()), [])
    return list(raw) if isinstance(raw, list) else []


def _r(var: str, val: Any, desc: str) -> LDExportRow:
    return LDExportRow(_s(var), _s(val), _s(desc))


def build_ld_rows_from_user_inputs(
    user_inputs: Mapping[str, Any],
    lift_index: int = 0,
) -> List[LDExportRow]:
    lift = _lift(user_inputs, lift_index)
    forces = _forces(user_inputs, lift_index)
    drive = _drive(user_inputs, lift_index)
    cost = _cost(user_inputs, lift_index)
    lop = lift.get("LOP type and location", lift.get("LOP type and locaion", ""))
    lip = lift.get("LIP type and location", "")
    rows: List[LDExportRow] = []

    rows += [
        _r("Shaft0.L_SystemTab.SYS_ELEV_DESC", lift.get("System Type", user_inputs.get("FileName", "")), "System designation name"),
        _r("Shaft0.L_SystemTab.SYS_ENTERED_LOAD", lift.get("Load capacity", lift.get("Load capacity (kg)", "")), "Load capacity"),
        _r(
            "Shaft0.L_SystemTab.SYS_ENTERED_PERSON",
            lift.get("Permissible number of persons", lift.get("Permissible number of persons (Pers.)", "")),
            "Permissible number of persons",
        ),
        _r("Shaft0.L_SystemTab.SYS_TRAVEL_SPEED_UP", lift.get("Speed", lift.get("Speed (m/s)", "")), "Speed"),
        _r("FLL.FLL_COUNT", lift.get("Stops", lift.get("Stops (Stck.)", "")), "Stops"),
        _r("Shaft0.Car.CW", lift.get("Cabin width", lift.get("Cabin width (mm)", "")), "Cabin width"),
        _r("Shaft0.Car.CD", lift.get("Cabin depth", lift.get("Cabin depth (mm)", "")), "Cabin depth"),
        _r("Shaft0.Car.HEIGHT", lift.get("Structural cabin height", lift.get("Structural cabin height (mm)", "")), "Structural cabin height"),
        _r("Shaft0.Entries1.E0.Opening.T_AUSBR_B", lift.get("Door structural opening width", lift.get("Door structural opening width (mm)", "")), "Door structural opening width"),
        _r("Shaft0.HEAD", lift.get("Shaft head suggested", lift.get("Shaft head suggested (mm)", "")), "Shaft head proposal"),
        _r("Shaft0.PIT", lift.get("Shaft pit suggested", lift.get("Shaft pit suggested (mm)", "")), "Shaft pit proposal"),
        _r("L_Projects.PROJ_USER_0", drive.get("Connected load", drive.get("Connected load (kVA)", "")), "Connected load"),
        _r("L_Projects.PROJ_USER_2", drive.get("Rated current", drive.get("Rated current (A)", "")), "Rated current"),
        _r("L_Projects.PROJ_USER_3", drive.get("Heat dissipation motor", drive.get("Heat dissipation motor (kJ)", "")), "Heat dissipation motor"),
        _r("Shaft0.Car.Frame.GuideList0.Force0.FZ", forces.get("Force F1, F2 elevator rail segment", forces.get("Force F1, F2 elevator rail segment (kN)", "")), "Force F1, F2 elevator rail segment"),
        _r("Shaft0.Car.Frame.GuideList1.Force0.FZ", forces.get("Force F1, F2 elevator rail segment", forces.get("Force F1, F2 elevator rail segment (kN)", "")), "Force F1, F2 elevator rail segment"),
        _r("Shaft0.Car.Frame.Buffer0.Force0.FZ", forces.get("Force F3, each buffer", forces.get("Force F3, each buffer (kN)", "")), "Force F3, each buffer"),
        _r("Shaft0.CW.Weight.GuideList0.Force0.FZ", forces.get("Force F4, per counterweight rail segment", forces.get("Force F4, per counterweight rail segment (kN)", "")), "Force F4, per counterweight rail segment"),
        _r("Shaft0.CW.Weight.Buffer0.Force0.FZ", forces.get("Force F5, per counterweight buffer", forces.get("Force F5, per counterweight buffer (kN)", "")), "Force F5, per counterweight buffer"),
        _r("Shaft0.Entries1.UBolt.Force0.FZ", forces.get("Force F6, static shaft door", forces.get("Force F6, static shaft door (kN)", "")), "Force F6, static shaft door"),
        _r("Shaft0.Entries2.UBolt.Force0.FZ", forces.get("Force F7, static counterweight", forces.get("Force F7, static counterweight (kN)", "")), "Force F7, static counterweight"),
        _r("Shaft0.Entries3.UBolt.Force0.FZ", forces.get("Force F8, static cabin", forces.get("Force F8, static cabin (kN)", "")), "Force F8, static cabin"),
        _r("Shaft0.Car.Frame.GuideList0.Force0.FX", forces.get("Force Fx, cabin rail", forces.get("Force Fx, cabin rail (kN)", "")), "Force Fx, cabin rail"),
        _r("Shaft0.Car.Frame.GuideList0.Force0.FY", forces.get("Force Fy, cabin rail", forces.get("Force Fy, cabin rail (kN)", "")), "Force Fy, cabin rail"),
        _r("Shaft0.CW.Weight.GuideList0.Force0.FX", forces.get("Force Fx, counterweight rail", forces.get("Force Fx, counterweight rail (kN)", "")), "Force Fx, counterweight rail"),
        _r("Shaft0.CW.Weight.GuideList0.Force0.FY", forces.get("Force Fy, counterweight rail", forces.get("Force Fy, counterweight rail (kN)", "")), "Force Fy, counterweight rail"),
        _r("L_StandardTab.STD_DESC", _compliance_summary(user_inputs, lift_index), "Applied codes"),
    ]

    z_cum = 0.0
    for idx, floor in enumerate(_floors(user_inputs, lift_index)):
        try:
            h_mm = float(str(floor.get("Height (m)", "0")).replace(",", ".")) * 1000.0
        except (ValueError, TypeError, OverflowError):
            h_mm = 0.0
        fname = _s(floor.get("Floor Name", floor.get("Floor", "")))
        label = fname if fname else f"Level {idx}"
        rows.append(_r(f"FLL.Level{idx}.Z_POT", str(int(round(z_cum))), label))
        z_cum += h_mm

    for idx, floor in enumerate(_floors(user_inputs, lift_index)):
        fn = _s(floor.get("Floor Name", ""))
        fl = _s(floor.get("Floor", ""))
        rows.append(_r(f"FLL.Level{idx}.DESC", fn, fl or fn))

    rows += [
        _r("LD.Cost.estimation", cost.get("Cost estimation", ""), "Cost estimation"),
        _r("LD.Cost.calculation", cost.get("Cost calculation", ""), "Cost calculation"),
        _r("Shaft0.Car.Frame.GuideList0.", forces.get("Rail weight car", forces.get("Rail weight car (kg/m)", "")), "Left rail"),
        _r("Shaft0.Car.Frame.GuideList1.", forces.get("Rail weight cwt", forces.get("Rail weight cwt (kg/m)", "")), "Right rail"),
        _r("Shaft0.W_1", lift.get("Cladding thickness each wall", lift.get("Cladding thickness each wall (mm)", "")), "Front wall"),
        _r("Shaft0.W_2", lift.get("Cladding thickness each wall", lift.get("Cladding thickness each wall (mm)", "")), "Rear wall"),
        _r("Shaft0.W_3", lift.get("Cladding thickness each wall", lift.get("Cladding thickness each wall (mm)", "")), "Left wall"),
        _r("Shaft0.W_4", lift.get("Cladding thickness each wall", lift.get("Cladding thickness each wall (mm)", "")), "Right wall"),
        _r("Shaft0.Entries1.E0.Opening.T_AUSBR_H", lift.get("Door structural opening height", lift.get("Door structural opening height (mm)", "")), "Front door opening height"),
        _r("Shaft0.Entries2.E0.Opening.T_AUSBR_H", lift.get("Door structural opening height", lift.get("Door structural opening height (mm)", "")), "Rear door opening height"),
        _r("", lift.get("Door structural opening width", lift.get("Door structural opening width (mm)", "")), "Structural door opening width"),
        _r("Shaft0.Entries2.E0.Opening.T_AUSBR_B", lift.get("Door structural opening width", lift.get("Door structural opening width (mm)", "")), "Structural door opening width"),
        _r("Shaft0.Entries1.E0.Panel0.", lop, "Front LOP panel type"),
        _r("Shaft0.Entries2.E0.Panel0.", lop, "Rear LOP panel type"),
        _r("Shaft0.Entries1.E0.Panel1.TABLEAU_POSITION", lip, "LIP location"),
    ]

    return rows


def _rows_to_matrix(rows: Sequence[LDExportRow]) -> List[List[str]]:
    out: List[List[str]] = [
        ["DTV_VARNAME", "DTV_VALUE", "DTV_MODE", "SYNC_MODE", "", "", ""],
    ]
    for r in rows:
        if not str(r.varname).strip() and not str(r.value).strip():
            continue
        out.append([r.varname, r.value, "0", "2", "", r.description, ""])
    return out


def write_ld_csv(path: str, rows: Sequence[LDExportRow]) -> None:
    matrix = _rows_to_matrix(rows)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for line in matrix:
            w.writerow(line)


def write_ld_workbook(path: str, rows: Sequence[LDExportRow]) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise ImportError("pip install openpyxl") from e
    wb = Workbook()
    ws = wb.active
    ws.title = "SyncWithLD"
    for r_idx, line in enumerate(_rows_to_matrix(rows), start=1):
        for c_idx, cell in enumerate(line, start=1):
            ws.cell(row=r_idx, column=c_idx, value=cell)
    wb.save(path)
