"""
Lift Designer backend parameters (non-UI).

This module groups configuration and calculation inputs into named sections.
Populate logic, defaults, and validation can be added here over time; the GUI
and other packages can import section identifiers and data structures.
"""
from __future__ import annotations

from enum import Enum, IntEnum
from typing import Any, Dict, Mapping, MutableMapping, Tuple

__all__ = [
    "ParameterSection",
    "SECTION_ORDER",
    "ShaftDepthOption",
    "SHAFT_DEPTH_OPTIONS_ORDER",
    "shaft_depth_label",
    "empty_parameter_bundle",
    "merge_parameter_bundle",
]


class ParameterSection(str, Enum):
    """Stable section ids for lift designer parameter data."""

    LIFT_DESIGNER_PARAMETERS = "lift_designer_parameters"
    WIDE_CABIN_FRONT_PANELS = "wide_cabin_front_panels"
    HANDRAIL = "handrail"
    COST = "cost"
    LEVEL_NAME_NUMERIC = "level_name_numeric"
    LEVEL_NAME_TEXT = "level_name_text"
    ENTRANCE_DOORS = "entrance_doors"
    CAR_DOORS = "car_doors"
    LIFT_ARRANGEMENT_TOOL = "lift_arrangement_tool"
    SHAFT_WIDTH = "shaft_width"
    SHAFT_DEPTH = "shaft_depth"
    RAIL = "rail"
    WALL_THICKNESS = "wall_thickness"
    DOOR_OPENING_HEIGHT = "door_opening_height"
    FRONT_DOOR = "front_door"
    REAR_DOOR = "rear_door"
    FRONT_LOP = "front_lop"
    REAR_LOP = "rear_lop"
    LIP = "lip"
    FLOOR_ENTRANCE_BOTTOM_RAILS = "floor_entrance_bottom_rails"
    FLOOR_ENTRANCE_TOP_RAIL = "floor_entrance_top_rail"
    REAR_ENTRANCE_RAILS = "rear_entrance_rails"
    TOP_RAILS = "top_rails"


class ShaftDepthOption(IntEnum):
    """
    Shaft depth arrangement (numbered options).

    1. Open Trough — ``OPEN_TROUGH``
    2. Front Entrance — ``FRONT_ENTRANCE``
    3. Rear Entrance — ``REAR_ENTRANCE``
    """

    OPEN_TROUGH = 1
    FRONT_ENTRANCE = 2
    REAR_ENTRANCE = 3


SHAFT_DEPTH_OPTIONS_ORDER: Tuple[ShaftDepthOption, ...] = (
    ShaftDepthOption.OPEN_TROUGH,
    ShaftDepthOption.FRONT_ENTRANCE,
    ShaftDepthOption.REAR_ENTRANCE,
)

_SHAFT_DEPTH_LABELS: Dict[ShaftDepthOption, str] = {
    ShaftDepthOption.OPEN_TROUGH: "Open Trough",
    ShaftDepthOption.FRONT_ENTRANCE: "Front Entrance",
    ShaftDepthOption.REAR_ENTRANCE: "Rear Entrance",
}


def shaft_depth_label(option: ShaftDepthOption) -> str:
    """Human-readable label for a shaft depth option (matches 1 / 2 / 3 naming)."""
    return _SHAFT_DEPTH_LABELS[option]


# Logical order for docs and tooling; adjust as workflows evolve.
SECTION_ORDER: Tuple[ParameterSection, ...] = (
    ParameterSection.LIFT_DESIGNER_PARAMETERS,
    ParameterSection.WIDE_CABIN_FRONT_PANELS,
    ParameterSection.HANDRAIL,
    ParameterSection.COST,
    ParameterSection.LEVEL_NAME_NUMERIC,
    ParameterSection.LEVEL_NAME_TEXT,
    ParameterSection.ENTRANCE_DOORS,
    ParameterSection.CAR_DOORS,
    ParameterSection.LIFT_ARRANGEMENT_TOOL,
    ParameterSection.SHAFT_WIDTH,
    ParameterSection.SHAFT_DEPTH,
    ParameterSection.RAIL,
    ParameterSection.WALL_THICKNESS,
    ParameterSection.DOOR_OPENING_HEIGHT,
    ParameterSection.FRONT_DOOR,
    ParameterSection.REAR_DOOR,
    ParameterSection.FRONT_LOP,
    ParameterSection.REAR_LOP,
    ParameterSection.LIP,
    ParameterSection.FLOOR_ENTRANCE_BOTTOM_RAILS,
    ParameterSection.FLOOR_ENTRANCE_TOP_RAIL,
    ParameterSection.REAR_ENTRANCE_RAILS,
    ParameterSection.TOP_RAILS,
)


def empty_parameter_bundle() -> Dict[str, Dict[str, Any]]:
    """Return one empty dict per section (keys are ``ParameterSection.value``)."""
    return {section.value: {} for section in ParameterSection}


def merge_parameter_bundle(
    base: Mapping[str, Mapping[str, Any]],
    updates: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Shallow-merge ``updates`` into a copy of ``base`` per section.
    Unknown section keys in ``updates`` are preserved.
    """
    out: Dict[str, Dict[str, Any]] = {
        k: dict(v) for k, v in base.items()
    }
    for section_key, payload in updates.items():
        bucket: MutableMapping[str, Any] = out.setdefault(section_key, {})
        bucket.update(payload)
    return out
