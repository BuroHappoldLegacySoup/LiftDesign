"""
Lift system types and load-capacity profiles (callable from GUI or scripts).

Use ``load_profile_for_capacity(load_kg)`` to get a profile instance; call
``cabin_width_mm(cabin_shape)`` for auto cabin width rules (None = no rule),
``cabin_depth_mm(cabin_width)`` for depth from nominal width (None = do not change).
"""
from __future__ import annotations

from typing import Optional, Tuple, Type


def _parse_width_mm(cabin_width: str) -> Optional[int]:
    t = (cabin_width or "").strip()
    if not t:
        return None
    try:
        return int(round(float(t.replace(",", "."))))
    except (ValueError, TypeError, OverflowError):
        return None


class LiftSystemType:
    """Labels used in General specification — System Type row."""

    PASSENGER = "Passenger Lift"
    SERVICE = "Service Lift"
    WASTE = "Waste Lift"
    FREIGHT = "Freight Lift"
    ALL: Tuple[str, ...] = (PASSENGER, SERVICE, WASTE, FREIGHT)


# Standard load capacities offered in the UI (kg)
LOAD_CAPACITY_KG: Tuple[int, ...] = (
    630, 1000, 1275, 1350, 1600, 1850, 2000, 2500, 3500,
)


class LiftLoadProfile:
    """Base profile for one nominal load capacity (kg)."""

    capacity_kg: int = 0

    def cabin_width_mm(self, cabin_shape: str) -> Optional[str]:
        """
        If this capacity has a fixed cabin width rule, return the value (or message).
        Return None to leave cabin width user-defined.
        """
        return None

    def cabin_depth_mm(self, cabin_width: str) -> Optional[str]:
        """
        If this capacity maps cabin width (mm) to depth, return depth or message.
        Return None when width is blank or non-numeric (do not overwrite the field).
        """
        return None


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


class LiftLoadDefault(LiftLoadProfile):
    """Any capacity without dedicated rules."""

    def __init__(self, capacity_kg: int = 0) -> None:
        self.capacity_kg = capacity_kg


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
    """
    Return the profile class instance for the given load (int, float, or numeric string).
    Unknown capacities use ``LiftLoadDefault`` (no cabin width auto-rule).
    """
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
    """Convenience: same as ``load_profile_for_capacity(load_kg).cabin_width_mm(cabin_shape)``."""
    return load_profile_for_capacity(load_kg).cabin_width_mm(cabin_shape)


def cabin_depth_for_load_and_width(load_kg: object, cabin_width: str) -> Optional[str]:
    """Convenience: ``load_profile_for_capacity(load_kg).cabin_depth_mm(cabin_width)``."""
    return load_profile_for_capacity(load_kg).cabin_depth_mm(cabin_width)


def register_load_profile(capacity_kg: int, profile_cls: Type[LiftLoadProfile]) -> None:
    """Register or replace a profile class for a capacity (e.g. from tests or plugins)."""
    _REGISTRY[int(capacity_kg)] = profile_cls
