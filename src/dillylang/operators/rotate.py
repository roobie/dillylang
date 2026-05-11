"""RotateOperator: change the axis of inquiry with implicit-subject probe.

Wraps BaseDSPyOperator with the rotate-specific prompt and schema.
The key quality gate: probe for the implicit subject of the original
framing and rotate to alternatives.

Spec reference: INDEX.md section 6 (rotate schema).
Steering parameter: target_frame (optional, via ADR-007).
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import RotateInput, RotateOutput

# Spec section 6 docstring with the implicit-subject probe instruction.
_ROTATE_DOCSTRING = (
    "Change the axis of inquiry. Each rotation must name a new axis "
    "explicitly. Probe for the implicit subject of the original framing "
    "-- who or what is being centered -- and rotate to alternatives. "
    "This is where rotate's leverage lives. Classify each rotation as "
    "axis_change (changing what dimension is examined) or viewpoint_change "
    "(changing who is examining). If target_frame is provided, orient "
    "rotations toward that frame of reference."
)


class RotateOperator(BaseDSPyOperator):
    """Frame rotation operator: change what axis or viewpoint examines a problem.

    Produces an original_axis (the detected frame) and a list of rotations,
    each classified as axis_change or viewpoint_change. The target_frame
    steering parameter narrows rotation direction when bound.
    """

    def __init__(self) -> None:
        super().__init__(
            name="rotate",
            docstring=_ROTATE_DOCSTRING,
            input_model=RotateInput,
            output_model=RotateOutput,
        )
