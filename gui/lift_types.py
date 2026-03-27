"""
Lift system types and per-capacity rules mirroring ``VT standard configurations`` Excel
(columns M–U ↔ loads 630 … 3500 kg).

Use ``load_profile_for_capacity(load_kg)`` for the profile instance; methods return
``None`` when the UI should not overwrite the cell.
"""
from __future__ import annotations

from typing import Optional, Tuple, Type


def _parse_width_mm(text: str) -> Optional[int]:
    t = (text or "").strip()
    if not t:
        return None
    try:
        return int(round(float(t.replace(",", "."))))
    except (ValueError, TypeError, OverflowError):
        return None


def _parse_height_mm(text: str) -> Optional[float]:
    """Numeric cabin/door height (mm); fails on status messages."""
    t = (text or "").strip()
    if not t:
        return None
    try:
        return float(t.replace(",", "."))
    except (ValueError, TypeError, OverflowError):
        return None


def _fmt_dim_str(x: float) -> str:
    if abs(x - round(x)) < 1e-6:
        return str(int(round(x)))
    return str(round(x, 2))


# Excel row 35 (cladding thickness each wall) — constants per column M–U ↔ load kg
CLADDING_THICKNESS_MM_BY_CAPACITY: dict[int, str] = {
    630: "0",
    1000: "0",
    1275: "0",
    1600: "0",
    1350: "10",
    1850: "10",
    2000: "10",
    2500: "10",
    3500: "10",
}

def _norm_access(access: str) -> str:
    return " ".join((access or "").strip().split()).lower()


def _access_through_front_rear_combo(access: str) -> bool:
    n = _norm_access(access)
    return n in ("front + rear", "front + side + rear")


def _access_front_or_rear_only(access: str) -> bool:
    return _norm_access(access) in ("front", "rear")


def _cwt_side_code(cwt_location: str) -> Optional[str]:
    m = (cwt_location or "").strip()
    if m == "CWT-Left":
        return "2L"
    if m == "CWT-Right":
        return "2R"
    return None


def _accessible_rooms_yes(value: object) -> bool:
    return str(value or "").strip().lower() == "yes"


def _parse_speed_m_s(raw: object) -> Optional[float]:
    t = str(raw or "").strip().replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except (ValueError, TypeError, OverflowError):
        return None


def _speed_eq(speed: float, target: float) -> bool:
    return abs(speed - target) < 0.021


def _shaft_head_raw(structural_mm: float, speed_m_s: float, arrangement_over_500: bool) -> float:
    """Excel row 59 inner expression before ROUND(..., 0)."""
    s = speed_m_s
    dyn = 0.035 * s * s * 1000.0
    if arrangement_over_500:
        if s > 1.6:
            return structural_mm + 250.0 + 150.0 + 1100.0 + 300.0 + dyn
        if s < 1.6:
            return structural_mm + 100.0 + 100.0 + 1100.0 + 300.0 + dyn
        return structural_mm + 200.0 + 120.0 + 1100.0 + 300.0 + dyn
    if s > 1.6:
        return structural_mm + 250.0 + 150.0 + 1000.0 + dyn
    if s < 1.6:
        return structural_mm + 100.0 + 100.0 + 1000.0 + dyn
    return structural_mm + 200.0 + 120.0 + 1000.0 + dyn


# --- Excel row 61 (shaft pit suggested): columns M–U ↔ row 20 load kg 630…3500 ---
# Row 22 in each column = Speed (m/s). M–Q also branch on row 20 vs 1600:
#   M–P (630–1350): load < 1600 → nested IF on {col}22 → 1600/1200/1400 or "non std. Speed".
#   Q (1600): load < 1600 is false → nested IF on Q22 → 1800/1400/1600 or "non std. Speed".
# R–S (1850, 2000): IF({col}22=2,1850, IF(1,1500, IF(1.6,1700,"non std. Speed"))).
# T (2500): IF(T22=2,1850, IF(1,1600, IF(1.6,1800,"non std. Speed"))).
# U (3500): IF(U22=1,1600,"non std. Speed").


def _pit_row_61_branch_under_1600(speed: float) -> str:
    """Excel row 61 inner branch when ``{col}20 < 1600`` (columns M–P). Uses row 22 (speed)."""
    if _speed_eq(speed, 2.0):
        return "1600"
    if _speed_eq(speed, 1.0):
        return "1200"
    if _speed_eq(speed, 1.6):
        return "1400"
    return "non std. Speed"


def _pit_row_61_branch_1600_and_up(speed: float) -> str:
    """Excel row 61 else-branch when ``{col}20 >= 1600`` (column Q at 1600 kg). Uses row 22 (speed)."""
    if _speed_eq(speed, 2.0):
        return "1800"
    if _speed_eq(speed, 1.0):
        return "1400"
    if _speed_eq(speed, 1.6):
        return "1600"
    return "non std. Speed"


def _pit_row_61_excel_column_r_or_s(speed: float) -> str:
    """Excel row 61, columns R–S (1850 / 2000 kg). Depends only on row 22 (speed)."""
    if _speed_eq(speed, 2.0):
        return "1850"
    if _speed_eq(speed, 1.0):
        return "1500"
    if _speed_eq(speed, 1.6):
        return "1700"
    return "non std. Speed"


def _pit_row_61_excel_column_t(speed: float) -> str:
    """Excel row 61, column T (2500 kg). Depends only on row 22 (speed)."""
    if _speed_eq(speed, 2.0):
        return "1850"
    if _speed_eq(speed, 1.0):
        return "1600"
    if _speed_eq(speed, 1.6):
        return "1800"
    return "non std. Speed"


def _pit_row_61_excel_column_u(speed: float) -> str:
    """Excel row 61, column U (3500 kg). Depends only on row 22 (speed); only 1.0 m/s is standard."""
    if _speed_eq(speed, 1.0):
        return "1600"
    return "non std. Speed"


class LiftSystemType:
    """Labels used in General specification — System Type row."""

    PASSENGER = "Passenger Lift"
    SERVICE = "Service Lift"
    WASTE = "Waste Lift"
    FREIGHT = "Freight Lift"
    ALL: Tuple[str, ...] = (PASSENGER, SERVICE, WASTE, FREIGHT)


LOAD_CAPACITY_KG: Tuple[int, ...] = (
    630, 1000, 1275, 1350, 1600, 1850, 2000, 2500, 3500,
)


class LiftLoadProfile:
    """Base profile for one nominal load capacity (kg)."""

    capacity_kg: int = 0

    def cabin_width_mm(self, cabin_shape: str) -> Optional[str]:
        return None

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        return None

    def clear_cabin_height_mm(self, cabin_width: str) -> Optional[str]:
        """Excel row 36 — constant or formula per load class; ``None`` = do not overwrite."""
        return None

    def door_width_mm(self, cabin_width: str) -> Optional[str]:
        """Excel row 40."""
        return None

    def cladding_thickness_mm(self) -> Optional[str]:
        """Excel row 35 — default mm per load column."""
        return CLADDING_THICKNESS_MM_BY_CAPACITY.get(self.capacity_kg)

    def structural_cabin_height_mm(self, clear_cabin_height_str: str) -> Optional[str]:
        """Excel row 37 — usually clear + 100; 2500 kg is fixed 2500 (column T)."""
        v = _parse_height_mm(clear_cabin_height_str)
        if v is None:
            return None
        return _fmt_dim_str(v + 100.0)

    def door_height_mm(self, clear_cabin_height_str: str) -> Optional[str]:
        """Excel row 42 — usually clear − 100; 3500 kg is fixed 2300 (column U)."""
        v = _parse_height_mm(clear_cabin_height_str)
        if v is None:
            return None
        return _fmt_dim_str(v - 100.0)

    def door_structural_opening_height_mm(self, door_height_str: str) -> Optional[str]:
        """Excel row 43 — door height + 140."""
        v = _parse_height_mm(door_height_str)
        if v is None:
            return None
        return _fmt_dim_str(v + 140.0)

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        """Excel row 44 (door type code)."""
        return None

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        """Excel row 53."""
        return None

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        """Excel row 57."""
        return None

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        """Excel row 290; ``None`` → shaft head uses the ``X290<=500`` branch."""
        return None

    def shaft_head_suggested_mm(
        self,
        structural_height_str: str,
        speed_m_s_raw: object,
        cabin_width_str: str,
        door_width_str: str,
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[str]:
        """Excel row 59 (``ROUND(..., 0)``)."""
        struct = _parse_height_mm(structural_height_str)
        if struct is None:
            return None
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        cw = _parse_width_mm(cabin_width_str)
        dw = _parse_width_mm(door_width_str)
        dt = (door_type_code or "").strip()
        arr = self.shaft_arrangement_clearance_mm(
            cw, dw, dt, float(cladding_mm), accessible_rooms_yes
        )
        tall = arr is not None and arr > 500.0
        return str(int(round(_shaft_head_raw(struct, sp, tall))))

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """
        Excel row 61 (shaft pit suggested). Each concrete profile implements the formula for
        its load column (M–U ↔ 630–3500 kg); inputs are template row 22 (Speed m/s) and,
        for M–Q, the load threshold in row 20 (encoded by the profile class).
        """
        return None

    # --- Mechanical loading (Excel rows 90–105); M20 = nominal load (kg) for column M–U ---

    def force_f1_f2_elevator_rail_segment_kn(self, travel_height_m: float) -> Optional[int]:
        """
        Excel row 91 — Force F1, F2 elevator rail segment (kN).

        ``=ROUND((M25/2*600+2.3*M20*9.81)/1000,0)+1`` where **M25** is travel height (m)
        and **M20** is load capacity (kg), i.e. ``self.capacity_kg`` for this lift type column.
        """
        if travel_height_m <= 0.0:
            return None
        m_kg = float(self.capacity_kg)
        g = 9.81
        return int(round((travel_height_m / 2.0 * 600.0 + 2.3 * m_kg * g) / 1000.0)) + 1

    # --- Electrical & HVAC (Excel rows 79–86; same structure for columns M–U) ---
    _ELEC_V_LINE_V = 400.0 * 1.732 * 0.85  # denominator for rated current (row 81)

    def motor_power_kw_from_persons(self, permissible_persons: float) -> float:
        """Row 79: ``1.5 * M21`` (permissible persons)."""
        return 1.5 * float(permissible_persons)

    def connected_load_kva(self, motor_power_kw: float) -> float:
        """Row 80: ``M79 + 1.5``."""
        return float(motor_power_kw) + 1.5

    def rated_current_a(self, motor_power_kw: float) -> float:
        """Row 81: ``M79*1000/(400*1.732*0.85)``."""
        return float(motor_power_kw) * 1000.0 / self._ELEC_V_LINE_V

    def starting_current_a(self, rated_current_a: float) -> float:
        """Row 82: ``M81 * 2``."""
        return float(rated_current_a) * 2.0

    def energy_consumption_kwh(self, motor_power_kw: float, duty_cycle_pct: float) -> float:
        """Row 85: ``M79/100*M78``."""
        return float(motor_power_kw) / 100.0 * float(duty_cycle_pct)

    def heat_dissipation_motor_kj(self, energy_consumption_kwh: float) -> float:
        """Row 86: ``0.5*M85*3600``."""
        return 0.5 * float(energy_consumption_kwh) * 3600.0


def _fmt_electrical_num(x: float, decimals: int = 2) -> str:
    if decimals <= 0:
        return str(int(round(x)))
    r = round(x, decimals)
    if abs(r - int(r)) < 10 ** (-decimals):
        return str(int(round(r)))
    return str(r)


# Defaults matching Excel template rows 73–77, 83–84, 87 (same for all load columns)
ELECTRICAL_HVAC_DEFAULTS: dict[str, str] = {
    "Drive/Motor location": "MRL top",
    "Drive/Motor type": "VVVF",
    "Power grid voltage/type (V)": "400",
    "Diversity factor (-)": "0.7",
    "Temperature machine room / shaft (°C)": "5-40",
}


def electrical_hvac_derived_for_lift(
    load_kg: object,
    permissible_persons: object,
    duty_cycle_pct: object,
) -> dict[str, str]:
    """
    Compute Excel-derived fields for one lift. Formulas are identical for every
    load column; ``load_kg`` selects the profile so a subclass can override if a
    future capacity uses a different expression.
    """
    prof = load_profile_for_capacity(load_kg)
    try:
        raw_p = str(permissible_persons or "").strip().replace(",", ".")
        if not raw_p:
            return {}
        persons = float(raw_p)
    except (ValueError, TypeError, OverflowError):
        return {}

    p_kw = prof.motor_power_kw_from_persons(persons)
    kva = prof.connected_load_kva(p_kw)
    i_r = prof.rated_current_a(p_kw)
    i_s = prof.starting_current_a(i_r)

    out: dict[str, str] = {
        "Drive/Motor Power (kW)": _fmt_electrical_num(p_kw, 2),
        "Connected load (kVA)": _fmt_electrical_num(kva, 2),
        "Rated current (A)": _fmt_electrical_num(i_r, 2),
        "Starting current (factor ≈ 2) (A)": _fmt_electrical_num(i_s, 2),
    }

    try:
        raw_d = str(duty_cycle_pct or "").strip().replace(",", ".")
        if raw_d:
            dc = float(raw_d)
            e85 = prof.energy_consumption_kwh(p_kw, dc)
            h86 = prof.heat_dissipation_motor_kj(e85)
            out["Energy consumption (kWh)"] = _fmt_electrical_num(e85, 4)
            out["Heat dissipation motor (kJ)"] = _fmt_electrical_num(h86, 2)
    except (ValueError, TypeError, OverflowError):
        pass

    return out


# --- Mechanical loading (Excel ``VT Standard configs`` rows 90–105) ---

MECHANICAL_RAIL_WEIGHT_CAR_KG_M: dict[int, int] = {
    630: 14,
    1000: 14,
    1275: 14,
    1350: 14,
    1600: 14,
    1850: 14,
    2000: 18,
    2500: 18,
    3500: 18,
}

MECHANICAL_RAIL_WEIGHT_CWT_KG_M: dict[int, int] = {
    630: 4,
    1000: 4,
    1275: 4,
    1350: 4,
    1600: 4,
    1850: 4,
    2000: 14,
    2500: 14,
    3500: 14,
}


def _mechanical_load_capacity_int(load_kg: object) -> Optional[int]:
    try:
        raw = str(load_kg).strip().replace(",", ".")
        if not raw:
            return None
        return int(round(float(raw)))
    except (ValueError, TypeError, OverflowError):
        return None


def _mechanical_positive_float(raw: object) -> Optional[float]:
    try:
        t = str(raw or "").strip().replace(",", ".")
        if not t:
            return None
        v = float(t)
        if v <= 0.0:
            return None
        return v
    except (ValueError, TypeError, OverflowError):
        return None


def mechanical_rail_weight_car_kg_m(load_kg: object) -> Optional[str]:
    n = _mechanical_load_capacity_int(load_kg)
    if n is None:
        return None
    v = MECHANICAL_RAIL_WEIGHT_CAR_KG_M.get(n)
    return str(v) if v is not None else None


def mechanical_rail_weight_cwt_kg_m(load_kg: object) -> Optional[str]:
    n = _mechanical_load_capacity_int(load_kg)
    if n is None:
        return None
    v = MECHANICAL_RAIL_WEIGHT_CWT_KG_M.get(n)
    return str(v) if v is not None else None


def mechanical_loading_derived_for_lift(
    load_kg: object,
    travel_height_m: object,
    cabin_width_mm: object,
    cabin_depth_mm: object,
    counterweight_safety_gear_yes: bool,
    num_car_buffers: object = 2.0,
    num_cwt_buffers: object = 2.0,
) -> dict[str, str]:
    """
    Same cell structure for columns M–U. Rail weights (rows 90, 96) are UI dropdowns; not included here.

    Row 91 (F1/F2 rail segment): implemented as ``LiftLoadProfile.force_f1_f2_elevator_rail_segment_kn``
    (same Excel formula for each column; **M20** / **M25** come from the profile and inputs).

    References (column M): row 93 ``=ROUND(2.3*M20*9.81/1000*4/M92,0)+1``, row 97–98, 100–101, 103–105 with ``M94``
    ``yes``/``no``; row 99 constant 20.

    Rows 93, 98, 100, 101 do **not** use travel height; they are still computed when ``M25`` is empty.
    Rows 91 and 97 require a positive travel height (``M25``).
    """
    load = _mechanical_load_capacity_int(load_kg)
    if load is None:
        return {}

    prof = load_profile_for_capacity(load_kg)

    n_car = _mechanical_positive_float(num_car_buffers)
    n_cwt = _mechanical_positive_float(num_cwt_buffers)
    if n_car is None or n_cwt is None:
        return {}

    th = _mechanical_positive_float(travel_height_m)

    g = 9.81
    m_kg = float(load)
    cwt_no = not counterweight_safety_gear_yes

    out: dict[str, str] = {}

    if th is not None:
        f1f2 = prof.force_f1_f2_elevator_rail_segment_kn(th)
        if f1f2 is not None:
            out["Force F1, F2 elevator rail segment (kN)"] = str(f1f2)
        if cwt_no:
            f4 = int(round((th / 2.5 * 600.0) / 1000.0)) + 1
        else:
            f4 = int(round((th / 2.5 * 600.0 + 1.7 * m_kg * g) / 1000.0)) + 1
        out["Force F4, per counterweight rail segment (kN)"] = str(f4)

    f3 = int(round(2.3 * m_kg * g / 1000.0 * 4.0 / n_car)) + 1
    f5 = int(round(1.7 * m_kg * g / 1000.0 * 4.0 / n_cwt))
    f6 = 20
    f7 = int(round(1.7 * m_kg * g / 1000.0)) + 1
    f8 = int(round(2.3 * m_kg * g / 1000.0)) + 1

    out["Force F3, each buffer (kN)"] = str(f3)
    out["Force F5, per counterweight buffer (kN)"] = str(f5)
    out["Force F6, static shaft door (kN)"] = str(f6)
    out["Force F7, static counterweight (kN)"] = str(f7)
    out["Force F8, static cabin (kN)"] = str(f8)

    cw = _parse_width_mm(str(cabin_width_mm or ""))
    cd = _parse_width_mm(str(cabin_depth_mm or ""))
    if cw is not None and cd is not None:
        cwf = float(cw)
        cdf = float(cd)
        # Rows 102–103 (cabin rail): ``M34`` = depth, ``M33`` = width.
        fx_cab = round((2.0 * g * m_kg * 0.2 * cdf / 2.0 / 2500.0 / 1000.0) + 0.1, 1)
        fy_cab = round((2.0 * g * m_kg * 0.2 * cwf / 2500.0 / 1000.0) + 0.1, 1)

        # Rows 104–105 (counterweight rail): ``IF(M94="no", 1.2*… , 2*… ) + 0.1``.
        if cwt_no:
            fx_cwt = round(1.2 * g * 1.5 * m_kg * 30.0 / 2.0 / 2000.0 / 1000.0 + 0.1, 1)
            fy_cwt = round(1.2 * g * 1.5 * m_kg * 41.0 / 2000.0 / 1000.0 + 0.1, 1)
        else:
            fx_cwt = round(2.0 * g * 1.5 * m_kg * 30.0 / 2.0 / 2000.0 / 1000.0 + 0.1, 1)
            fy_cwt = round(2.0 * g * 1.5 * m_kg * 41.0 / 2000.0 / 1000.0 + 0.1, 1)

        out["Force Fx, cabin rail (kN)"] = _fmt_electrical_num(fx_cab, 1)
        out["Force Fy, cabin rail (kN)"] = _fmt_electrical_num(fy_cab, 1)
        out["Force Fx, counterweight rail (kN)"] = _fmt_electrical_num(fx_cwt, 1)
        out["Force Fy, counterweight rail (kN)"] = _fmt_electrical_num(fy_cwt, 1)

    return out


class LiftLoad630(LiftLoadProfile):
    capacity_kg = 630

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        return "1100" if s == "Deep" else "non std. Cabin type"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        return "1400" if w == 1100 else "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel M36."""
        del cabin_width
        return "2200"

    def door_width_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        return "900" if w == 1100 else "non standard Car width"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        x = _cwt_side_code(cwt_location)
        return x if x is not None else "Non std. CTW"

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        del accessible_rooms_yes
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 1100:
            return str(int(1750 + cladding_mm * 2))
        return "non-std. cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d != 1400:
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return "2050"
        if _access_front_or_rear_only(access_type):
            return str(int(1800 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        del accessible_rooms_yes
        if cabin_width_mm == 1100 and door_width_mm == 900 and door_type_code in ("2L", "2R"):
            return 450.0 + float(cladding_mm)
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel M61 (630 kg): ``IF(M20<1600,…)`` → under-1600 branch; depends on row 22 (speed)."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_branch_under_1600(sp)


class LiftLoad1000(LiftLoadProfile):
    capacity_kg = 1000

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Deep":
            return "1100"
        if s == "Wide":
            return "1600"
        return "non std. Cabin type"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 1100:
            return "2100"
        if w == 1600:
            return "1400"
        return "non standard width"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel N36."""
        del cabin_width
        return "2200"

    def door_width_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 1100:
            return "900"
        if w == 1600:
            return "1000"
        return "non standard Car width"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w == 1600:
            return "2C"
        if w == 1100:
            x = _cwt_side_code(cwt_location)
            return x if x is not None else "wrong CWT"
        return None

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        c2 = cladding_mm * 2
        if w == 1100:
            return str(int(1750 + c2))
        if w == 1600:
            base = 2350 if accessible_rooms_yes else 2300
            return str(int(base + c2))
        return "non-std. cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d not in (1400, 2100):
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 500 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        c = float(cladding_mm)
        if cabin_width_mm == 1100 and door_width_mm == 900 and door_type_code in ("2L", "2R"):
            return 450.0 + c
        if cabin_width_mm == 1600 and door_width_mm == 1000 and door_type_code == "2C":
            if not accessible_rooms_yes:
                return 400.0 + c
            return 450.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel N61 (1000 kg): ``IF(N20<1600,…)``; depends on row 22 (speed)."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_branch_under_1600(sp)


class LiftLoad1275(LiftLoadProfile):
    capacity_kg = 1275

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Deep":
            return "1200"
        if s == "Wide":
            return "2000"
        return "Wrong shape"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 2000:
            return "1500"
        if w == 1200:
            return "2300"
        return "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel O36."""
        del cabin_width
        return "2300"

    def door_width_mm(self, cabin_width: str) -> str:
        """Excel O40 constant for column O (1275 kg)."""
        del cabin_width
        return "1100"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w == 2000:
            return "2C"
        if w == 1200:
            x = _cwt_side_code(cwt_location)
            return x if x is not None else "wrong CWT"
        return None

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        del accessible_rooms_yes
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        c2 = cladding_mm * 2
        if w == 1200:
            return str(int(2000 + c2))
        if w == 2000:
            return str(int(2800 + c2))
        return "non-std. cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d not in (1500, 2300):
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 500 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        del accessible_rooms_yes
        c = float(cladding_mm)
        if cabin_width_mm == 1200 and door_width_mm == 1100 and door_type_code in ("2L", "2R"):
            return 600.0 + c
        if cabin_width_mm == 2000 and door_width_mm == 1100 and door_type_code == "2C":
            return 550.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel O61 (1275 kg): ``IF(O20<1600,…)``; depends on row 22 (speed)."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_branch_under_1600(sp)


class LiftLoad1350(LiftLoadProfile):
    capacity_kg = 1350

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Wide":
            return "2000"
        return "non std. Cabin type"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        return "1500" if w == 2000 else "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel P36."""
        del cabin_width
        return "2300"

    def door_width_mm(self, cabin_width: str) -> str:
        """Excel P40 constant for column P (1350 kg)."""
        del cabin_width
        return "1100"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        del cwt_location
        w = _parse_width_mm(cabin_width)
        return "2C" if w == 2000 else None

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        del accessible_rooms_yes
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 2000:
            return str(int(2800 + cladding_mm * 2))
        return "non.std.cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d != 1500:
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 500 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        del accessible_rooms_yes
        c = float(cladding_mm)
        if cabin_width_mm == 2000 and door_width_mm == 1100 and door_type_code == "2C":
            return 550.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel P61 (1350 kg): ``IF(P20<1600,…)``; depends on row 22 (speed)."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_branch_under_1600(sp)


class LiftLoad1600(LiftLoadProfile):
    capacity_kg = 1600

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Deep":
            return "1400"
        if s == "Wide":
            return "2100"
        return "Wrong shape"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 1400:
            return "2400"
        if w == 2100:
            return "1600"
        return "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> Optional[str]:
        """Excel Q36: ``=IF(Q33=2100,2400,IF(Q33=1400,2300,"non std.CW"))`` (cabin width = Q33)."""
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 2100:
            return "2400"
        if w == 1400:
            return "2300"
        return "non std.CW"

    def door_width_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 1400:
            return "1300"
        if w == 2100:
            return "1200"
        return "non std.CW"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        del cwt_location
        w = _parse_width_mm(cabin_width)
        if w == 1400:
            return "4C"
        if w == 2100:
            return "2C"
        return "non std. SW"

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        c2 = cladding_mm * 2
        if w == 1400:
            base = 2300 if accessible_rooms_yes else 2350
            return str(int(base + c2))
        if w == 2100:
            return str(int(2900 + c2))
        return "non-std. cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d not in (1600, 2400):
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 500 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        c = float(cladding_mm)
        if cabin_width_mm == 1400 and door_width_mm == 1300 and door_type_code == "4C":
            return 500.0 + c
        if cabin_width_mm == 2100 and door_width_mm == 1300 and door_type_code == "4C" and not accessible_rooms_yes:
            return 550.0 + c
        if (
            cabin_width_mm == 2100
            and door_width_mm == 1200
            and door_type_code == "2C"
            and accessible_rooms_yes
        ):
            return 550.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel Q61 (1600 kg): ``IF(Q20<1600,…)`` is false → ≥1600 branch; depends on row 22 (speed)."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_branch_1600_and_up(sp)


class LiftLoad1850(LiftLoadProfile):
    capacity_kg = 1850

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Wide":
            return "2100"
        return "Wrong shape"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        return "1800" if w == 2100 else "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel R36."""
        del cabin_width
        return "2400"

    def door_width_mm(self, cabin_width: str) -> str:
        """Excel R40 constant for column R (1850 kg)."""
        del cabin_width
        return "1200"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        del cwt_location
        w = _parse_width_mm(cabin_width)
        return "2C" if w == 2100 else None

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        del accessible_rooms_yes
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 2100:
            return str(int(2900 + cladding_mm * 2))
        return "non std. Cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d != 1800:
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 500 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        del accessible_rooms_yes
        c = float(cladding_mm)
        if cabin_width_mm == 2100 and door_width_mm == 1200 and door_type_code == "2C":
            return 550.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel R61 (1850 kg); depends on row 22 (speed) only."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_excel_column_r_or_s(sp)


class LiftLoad2000(LiftLoadProfile):
    capacity_kg = 2000

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Deep":
            return "1500"
        return "Wrong shape"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        return "2700" if w == 1500 else "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel S36."""
        del cabin_width
        return "2300"

    def door_width_mm(self, cabin_width: str) -> str:
        """Excel S40 constant for column S (2000 kg)."""
        del cabin_width
        return "1300"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        del cwt_location
        w = _parse_width_mm(cabin_width)
        return "4C" if w == 1500 else None

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        del accessible_rooms_yes
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 1500:
            return str(int(2400 + cladding_mm * 2))
        return "non std. Cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d != 2700:
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 450 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        del accessible_rooms_yes
        c = float(cladding_mm)
        if cabin_width_mm == 1500 and door_width_mm == 1300 and door_type_code == "4C":
            return 575.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel S61 (2000 kg); depends on row 22 (speed) only (same formula as R)."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_excel_column_r_or_s(sp)


class LiftLoad2500(LiftLoadProfile):
    capacity_kg = 2500

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Deep":
            return "1800"
        return "Wrong shape"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        return "2700" if w == 1800 else "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel T36."""
        del cabin_width
        return "2300"

    def door_width_mm(self, cabin_width: str) -> str:
        """Excel T40 constant for column T (2500 kg)."""
        del cabin_width
        return "1500"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        del cwt_location
        w = _parse_width_mm(cabin_width)
        return "4C" if w == 1800 else None

    def structural_cabin_height_mm(self, clear_cabin_height_str: str) -> str:
        """Excel T37 fixed 2500 mm (not clear + 100)."""
        del clear_cabin_height_str
        return "2500"

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        del accessible_rooms_yes
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 1800:
            return str(int(2700 + cladding_mm * 2))
        return "non std. Cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d != 2700:
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 450 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        del accessible_rooms_yes
        c = float(cladding_mm)
        if cabin_width_mm == 1800 and door_width_mm == 1500 and door_type_code == "4C":
            return 650.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel T61 (2500 kg); depends on row 22 (speed) only."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_excel_column_t(sp)


class LiftLoad3500(LiftLoadProfile):
    capacity_kg = 3500

    def cabin_width_mm(self, cabin_shape: str) -> str:
        s = (cabin_shape or "").strip()
        if s == "Deep":
            return "2100"
        return "Wrong shape"

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        return "3000" if w == 2100 else "non std. Cabin type"

    def clear_cabin_height_mm(self, cabin_width: str) -> str:
        """Excel U36."""
        del cabin_width
        return "2400"

    def door_width_mm(self, cabin_width: str) -> str:
        """Excel U40 constant for column U (3500 kg)."""
        del cabin_width
        return "1800"

    def door_type_code(self, cabin_width: str, cwt_location: str) -> Optional[str]:
        del cwt_location
        w = _parse_width_mm(cabin_width)
        return "4C" if w == 2100 else None

    def door_height_mm(self, clear_cabin_height_str: str) -> str:
        """Excel U42 fixed 2300 mm (not clear − 100)."""
        del clear_cabin_height_str
        return "2300"

    def shaft_width_suggested_mm(
        self, cabin_width: str, cladding_mm: float, accessible_rooms_yes: bool
    ) -> Optional[str]:
        del accessible_rooms_yes
        w = _parse_width_mm(cabin_width)
        if w is None:
            return None
        if w == 2100:
            return str(int(3300 + cladding_mm * 2))
        return "non std. Cabin width"

    def shaft_depth_suggested_mm(
        self, cabin_depth: str, cladding_mm: float, access_type: str
    ) -> Optional[str]:
        d = _parse_width_mm(cabin_depth)
        if d is None:
            return None
        if d != 3000:
            return "non-std.cabin depth"
        if _access_through_front_rear_combo(access_type):
            return str(int(d + 650))
        if _access_front_or_rear_only(access_type):
            return str(int(d + 450 + cladding_mm))
        return "non-std.cabin depth"

    def shaft_arrangement_clearance_mm(
        self,
        cabin_width_mm: Optional[int],
        door_width_mm: Optional[int],
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[float]:
        del accessible_rooms_yes
        c = float(cladding_mm)
        if cabin_width_mm == 2100 and door_width_mm == 1800 and door_type_code == "4C":
            return 750.0 + c
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """Excel U61 (3500 kg); depends on row 22 (speed) only."""
        sp = _parse_speed_m_s(speed_m_s_raw)
        if sp is None:
            return None
        return _pit_row_61_excel_column_u(sp)


class LiftLoadDefault(LiftLoadProfile):
    """Any capacity without dedicated rules."""

    def __init__(self, capacity_kg: int = 0) -> None:
        self.capacity_kg = capacity_kg

    def shaft_head_suggested_mm(
        self,
        structural_height_str: str,
        speed_m_s_raw: object,
        cabin_width_str: str,
        door_width_str: str,
        door_type_code: str,
        cladding_mm: float,
        accessible_rooms_yes: bool,
    ) -> Optional[str]:
        return None

    def shaft_pit_suggested_mm(self, speed_m_s_raw: object) -> Optional[str]:
        """No Excel column mapping for this capacity; row 61 not applied."""
        return None


_REGISTRY: dict[int, Type[LiftLoadProfile]] = {
    630: LiftLoad630,
    1000: LiftLoad1000,
    1275: LiftLoad1275,
    1350: LiftLoad1350,
    1600: LiftLoad1600,
    1850: LiftLoad1850,
    2000: LiftLoad2000,
    2500: LiftLoad2500,
    3500: LiftLoad3500,
}


def load_profile_for_capacity(load_kg: object) -> LiftLoadProfile:
    try:
        raw = str(load_kg).strip().replace(",", ".")
        if not raw:
            return LiftLoadDefault(0)
        n = int(round(float(raw)))
    except (ValueError, TypeError, OverflowError):
        return LiftLoadDefault(0)

    cls = _REGISTRY.get(n)
    if cls is not None:
        return cls()
    return LiftLoadDefault(n)


def cabin_width_for_load_and_shape(load_kg: object, cabin_shape: str) -> Optional[str]:
    return load_profile_for_capacity(load_kg).cabin_width_mm(cabin_shape)


def cabin_depth_for_load_and_width(load_kg: object, cabin_width: str) -> Optional[str]:
    return load_profile_for_capacity(load_kg).cabin_depth_mm(cabin_width)


def register_load_profile(capacity_kg: int, profile_cls: Type[LiftLoadProfile]) -> None:
    _REGISTRY[int(capacity_kg)] = profile_cls
