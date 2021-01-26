from thingtalk import Property, Value
from .schemas import Binary, Numeric, Enum, Text, Composite


def visit_binary(data: Binary):
    if data.value_on == "ON":
        base_metadata = {
            "@type": "BooleanProperty",
            "title": data.name,
            "type": "string",
            "enum": ["ON", "OFF"],
        }
        if data.value_toggle:
            base_metadata.update({"enum": ["ON", "OFF", "TOGGLE"]})

        if data.description:
            base_metadata.update({"description": data.description})
    else:
        base_metadata = {
            "@type": "BooleanProperty",
            "title": data.name,
            "type": "boolean",
        }
        if data.description:
            base_metadata.update({"description": data.description})
    return base_metadata, Property(
        data.name, Value(data.value_off), metadata=base_metadata
    )


def visit_numeric(data: Numeric):
    min_value = 0
    base_metadata = {
        "@type": "NumberProperty",
        "title": data.name,
        "type": "number",
    }

    if data.value_max:
        base_metadata.update({"maximum": data.value_max})

    if data.value_min is not None:
        base_metadata.update({"minimum": data.value_min})
        min_value = data.value_min

    if data.unit:
        base_metadata.update({"unit": data.unit})

    if data.description:
        base_metadata.update({"description": data.description})

    return base_metadata, Property(data.name, Value(min_value), metadata=base_metadata)


def visit_enum(data: Enum):
    base_metadata = {
        "@type": "EnumProperty",
        "title": data.name,
        "type": "string",
        "enum": data.values,
    }
    if data.description:
        base_metadata.update({"description": data.description})

    return base_metadata, Property(data.name, Value(""), metadata=base_metadata)


def visit_text(data: Text):
    base_metadata = {
        "@type": "TextProperty",
        "title": data.name,
        "type": "string",
    }
    if data.description:
        base_metadata.update({"description": data.description})

    return base_metadata, Property(data.name, Value(""), metadata=base_metadata)


def visit_composite(data: Composite):
    base_metadata = {
        "@type": "CompositeProperty",
        "type": "object",
        "title": data.name,
        "properties": {data.name: {"type": "object", "properties": {}}},
    }
    if data.description:
        base_metadata.update({"description": data.description})
    for feature in data.features:
        if isinstance(feature, Numeric):
            _schema, _ = visit_numeric(feature)
        elif isinstance(feature, Binary):
            _schema, _ = visit_binary(feature)
        elif isinstance(feature, Enum):
            _schema, _ = visit_enum(feature)
        else:
            _schema, _ = visit_text(feature)
        base_metadata["properties"][data.name]["properties"].update(
            {feature.name: _schema}
        )
    return base_metadata, Property(data.name, Value({}), metadata=base_metadata)
