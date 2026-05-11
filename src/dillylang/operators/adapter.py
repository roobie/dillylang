"""Vocab-to-DSPy adapter: converts Pydantic schemas to DSPy Signatures and back.

This is the core boundary layer. Vocabulary types flow in, get converted
to DSPy Signatures for LLM execution, and results flow back as vocabulary
types. The vocabulary layer never sees DSPy; this module handles all
translation.

Key functions:
  - vocab_schema_to_signature: Pydantic models -> DSPy Signature class
  - prediction_to_vocab_output: DSPy Prediction -> Pydantic model instance
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from typing import Any, get_args, get_origin, get_type_hints

import dspy
from pydantic import BaseModel, ValidationError


def _enrich_desc_for_complex_type(desc: str, field_type: Any) -> str:
    """Append structural hints when a field's type is a Pydantic model.

    Small models struggle to produce nested JSON without explicit guidance.
    This adds "JSON object with keys: ..." to the description so the model
    knows the expected shape from the field description alone.
    """
    model_cls = _extract_pydantic_model(field_type)
    if model_cls is None:
        return desc

    fields = model_cls.model_fields
    parts = []
    for name, info in fields.items():
        field_desc = info.description or name
        parts.append(f"'{name}' ({field_desc})")
    schema_hint = ", ".join(parts)

    is_list = get_origin(field_type) is list
    if is_list:
        return f"{desc}. Each item is a JSON object with keys: {schema_hint}"
    return f"{desc}. JSON object with keys: {schema_hint}"


def _extract_pydantic_model(field_type: Any) -> type[BaseModel] | None:
    """Extract the Pydantic model class from a type annotation, if present."""
    # Direct model class
    if isinstance(field_type, type) and issubclass(field_type, BaseModel):
        return field_type
    # list[Model] or List[Model]
    origin = get_origin(field_type)
    if origin is list:
        args = get_args(field_type)
        if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
            return args[0]
    # Annotated[Model, ...] or Annotated[list[Model], ...]
    if origin is typing.Annotated:
        args = get_args(field_type)
        if args:
            return _extract_pydantic_model(args[0])
    return None


def vocab_schema_to_signature(
    name: str,
    docstring: str,
    input_model: type[BaseModel] | None,
    output_model: type[BaseModel],
    data_field_name: str = "problem_text",
    data_field_desc: str = "problem statement or upstream artifact",
) -> type[dspy.Signature]:
    """Build a DSPy Signature class from vocabulary Pydantic models.

    The generated signature always has a primary data InputField (the pipeline
    data channel). Steering parameters from input_model become additional
    InputFields. Output model fields become OutputFields with their Pydantic
    descriptions preserved.

    Complex output types (list[Axiom], etc.) use the Pydantic model type as
    the annotation -- DSPy's JSONAdapter handles Pydantic models as field types.

    Args:
        name: Signature class name (e.g. "DecomposeSignature").
        docstring: Prompt instruction rendered by DSPy as the task description.
        input_model: Optional Pydantic model for steering parameters. None means
            the operator takes only the data channel input.
        output_model: Pydantic model defining structured output fields.
        data_field_name: Name of the primary data InputField.
        data_field_desc: Description for the data InputField.

    Returns:
        A dynamically created dspy.Signature subclass.
    """
    annotations: dict[str, Any] = {}
    namespace: dict[str, Any] = {"__doc__": docstring}

    # Primary data channel -- always present
    annotations[data_field_name] = str
    namespace[data_field_name] = dspy.InputField(desc=data_field_desc)

    # Steering parameters from input_model (if provided)
    if input_model is not None:
        for field_name, field_info in input_model.model_fields.items():
            # Use the Pydantic field's annotation for the DSPy field type.
            # For optional fields, keep str as the annotation since DSPy
            # handles None defaults via the default= kwarg.
            annotations[field_name] = str
            desc = field_info.description or field_name
            namespace[field_name] = dspy.InputField(
                default=field_info.default,
                desc=desc,
            )

    # Output fields from output_model -- preserve Pydantic type annotations
    # so DSPy's JSONAdapter can validate complex types (list[Axiom], etc.)
    # Skip output fields that collide with an already-registered InputField.
    # DSPy Signatures don't support a field being both Input and Output.
    output_hints = get_type_hints(output_model)
    for field_name, field_info in output_model.model_fields.items():
        existing = namespace.get(field_name)
        if existing is not None and getattr(
            existing, "json_schema_extra", {}
        ).get("__dspy_field_type") == "input":
            continue  # already registered as steering input
        field_type = output_hints.get(field_name, Any)
        annotations[field_name] = field_type
        desc = field_info.description or field_name
        desc = _enrich_desc_for_complex_type(desc, field_type)
        namespace[field_name] = dspy.OutputField(desc=desc)

    namespace["__annotations__"] = annotations
    return type(name, (dspy.Signature,), namespace)


def prediction_to_vocab_output(
    prediction: dspy.Prediction,
    output_model: type[BaseModel],
) -> BaseModel:
    """Convert a DSPy Prediction to a vocabulary Pydantic model instance.

    Extracts field values from the prediction matching the output_model's
    declared fields, then constructs a validated instance via model_validate.

    Args:
        prediction: DSPy Prediction containing output field values.
        output_model: Target Pydantic model class to construct.

    Returns:
        A validated instance of output_model.
    """
    data = {}
    for field_name in output_model.model_fields:
        if hasattr(prediction, field_name):
            data[field_name] = getattr(prediction, field_name)
    return output_model.model_validate(data)


@dataclass
class FieldValidationError:
    """A single field-level validation failure from partial validation."""

    field_path: str
    raw_value: Any
    error_message: str
    valid_values: list[str] = field(default_factory=list)


@dataclass
class PartialValidationResult:
    """Result of partial validation: raw data + per-field errors.

    The raw_data dict contains everything the LLM produced (pre-validation).
    The errors list identifies which fields failed and why — enabling
    targeted repair of only the broken fields.
    """

    raw_data: dict[str, Any]
    errors: list[FieldValidationError]

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def is_enum_only(self) -> bool:
        """True if all errors are literal/enum mismatches (targeted-repair candidates)."""
        return self.has_errors and all(
            e.valid_values for e in self.errors
        )


def try_prediction_to_vocab_output(
    prediction: dspy.Prediction,
    output_model: type[BaseModel],
) -> PartialValidationResult:
    """Non-raising variant: returns raw data + field-level errors.

    Extracts all field values from the prediction, attempts validation,
    and on failure parses Pydantic's ValidationError to identify exactly
    which fields broke and what the valid options were.
    """
    data = {}
    for field_name in output_model.model_fields:
        if hasattr(prediction, field_name):
            data[field_name] = getattr(prediction, field_name)

    try:
        output_model.model_validate(data)
        return PartialValidationResult(raw_data=data, errors=[])
    except ValidationError as exc:
        errors = _extract_field_errors(exc)
        return PartialValidationResult(raw_data=data, errors=errors)


def _extract_field_errors(exc: ValidationError) -> list[FieldValidationError]:
    """Parse Pydantic ValidationError into structured per-field errors."""
    errors: list[FieldValidationError] = []
    for err in exc.errors():
        loc_parts = [str(p) for p in err.get("loc", [])]
        field_path = ".".join(loc_parts)

        # Extract valid literal values from the error context if available
        valid_values: list[str] = []
        ctx = err.get("ctx", {})
        if "expected" in ctx:
            # Pydantic literal errors put expected values in ctx["expected"]
            # as a string like "'resolved', 'deferred' or 'accepted_as_tradeoff'"
            expected = ctx["expected"]
            valid_values = [
                v.strip().strip("'\"")
                for v in expected.replace(" or ", ", ").split(",")
                if v.strip()
            ]

        # Retrieve the raw value via the location path
        raw_value = err.get("input", None)

        errors.append(FieldValidationError(
            field_path=field_path,
            raw_value=raw_value,
            error_message=err.get("msg", ""),
            valid_values=valid_values,
        ))
    return errors
