import warnings

import pytest

import betterosi
import betterosi.deprecation as dep


def test_enum_original_name_warning():
    with pytest.deprecated_call(match="original name 'TYPE_UNKNOWN'"):
        val = betterosi.MovingObjectType.TYPE_UNKNOWN
    assert val == betterosi.MovingObject.Type.UNKNOWN


def test_enum_modern_name_no_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        val = betterosi.MovingObjectType.UNKNOWN
    assert val == betterosi.MovingObject.Type.UNKNOWN


def test_enum_wrapped_property_warning():
    with pytest.deprecated_call(match=r"Accessing \.wrapped is deprecated\."):
        wrapped_cls = betterosi.MovingObjectType.wrapped
    assert wrapped_cls is betterosi.MovingObject.Type

    with pytest.deprecated_call(match=r"Accessing \.wrapped is deprecated\."):
        betterosi.MovingObjectType.wrapped = wrapped_cls


def test_enum_from_string_original_name_warning():
    with pytest.deprecated_call(match="original name 'TYPE_UNKNOWN'"):
        val = betterosi.MovingObjectType.from_string("TYPE_UNKNOWN")
    assert val == betterosi.MovingObject.Type.UNKNOWN

    with pytest.raises(ValueError, match="Unknown enum value"):
        betterosi.MovingObjectType.from_string("NON_EXISTENT_ENUM")


def test_enum_subscript_original_name_warning():
    with pytest.deprecated_call(match="original name 'TYPE_UNKNOWN'"):
        val = betterosi.MovingObjectType["TYPE_UNKNOWN"]
    assert val == betterosi.MovingObject.Type.UNKNOWN

    with pytest.raises(KeyError):
        _ = betterosi.MovingObjectType["NON_EXISTENT_ENUM"]


def test_enum_contains_original_name():
    with pytest.deprecated_call(match="Checking enum value by original name"):
        assert "TYPE_UNKNOWN" in betterosi.MovingObjectType

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert "UNKNOWN" in betterosi.MovingObjectType
        assert "NON_EXISTENT_ENUM" not in betterosi.MovingObjectType
        assert betterosi.MovingObject.Type.UNKNOWN in betterosi.MovingObjectType
        assert 0 in betterosi.MovingObjectType
        assert 999999 not in betterosi.MovingObjectType
        assert [] not in betterosi.MovingObjectType


def test_enum_type_and_subtype_prefixes():
    # 1. Access via SUBTYPE_* on an enum that originally had TYPE_*
    with pytest.deprecated_call(match="original name 'SUBTYPE_UNKNOWN'"):
        val_sub = betterosi.MovingObjectType.SUBTYPE_UNKNOWN
    assert val_sub == betterosi.MovingObject.Type.UNKNOWN

    with pytest.deprecated_call(match="original name 'SUBTYPE_VEHICLE'"):
        val_veh = betterosi.MovingObjectType.SUBTYPE_VEHICLE
    assert val_veh == betterosi.MovingObject.Type.VEHICLE

    # 2. Access via TYPE_* on an enum that originally had SUBTYPE_* (Lane.Classification.Subtype)
    with pytest.deprecated_call(match="original name 'TYPE_NORMAL'"):
        val_type_normal = betterosi.LaneClassificationSubtype.TYPE_NORMAL
    assert val_type_normal == betterosi.LaneClassification.Subtype.NORMAL

    with pytest.deprecated_call(match="original name 'SUBTYPE_NORMAL'"):
        val_sub_normal = betterosi.LaneClassificationSubtype.SUBTYPE_NORMAL
    assert val_sub_normal == betterosi.LaneClassification.Subtype.NORMAL

    # 3. Subscript and from_string with SUBTYPE_*
    with pytest.deprecated_call(match="original name 'SUBTYPE_UNKNOWN'"):
        assert (
            betterosi.MovingObjectType["SUBTYPE_UNKNOWN"]
            == betterosi.MovingObject.Type.UNKNOWN
        )

    with pytest.deprecated_call(match="original name 'SUBTYPE_UNKNOWN'"):
        assert (
            betterosi.MovingObjectType.from_string("SUBTYPE_UNKNOWN")
            == betterosi.MovingObject.Type.UNKNOWN
        )

    with pytest.deprecated_call(match="Checking enum value by original name"):
        assert "SUBTYPE_UNKNOWN" in betterosi.MovingObjectType

    # 4. Direct access on the enum class itself
    with pytest.deprecated_call(match="original name 'TYPE_UNKNOWN'"):
        assert (
            betterosi.MovingObject.Type.TYPE_UNKNOWN
            == betterosi.MovingObject.Type.UNKNOWN
        )

    with pytest.deprecated_call(match="original name 'SUBTYPE_UNKNOWN'"):
        assert (
            betterosi.MovingObject.Type.SUBTYPE_UNKNOWN
            == betterosi.MovingObject.Type.UNKNOWN
        )

    with pytest.deprecated_call(match="original name 'TYPE_NORMAL'"):
        assert (
            betterosi.LaneClassification.Subtype.TYPE_NORMAL
            == betterosi.LaneClassification.Subtype.NORMAL
        )

    with pytest.deprecated_call(match="original name 'SUBTYPE_NORMAL'"):
        assert (
            betterosi.LaneClassification.Subtype.SUBTYPE_NORMAL
            == betterosi.LaneClassification.Subtype.NORMAL
        )

    # 5. Subscript and contains on the enum class itself
    with pytest.deprecated_call(match="original name 'TYPE_UNKNOWN'"):
        assert (
            betterosi.MovingObject.Type["TYPE_UNKNOWN"]
            == betterosi.MovingObject.Type.UNKNOWN
        )

    with pytest.deprecated_call(match="original name 'SUBTYPE_UNKNOWN'"):
        assert (
            betterosi.MovingObject.Type["SUBTYPE_UNKNOWN"]
            == betterosi.MovingObject.Type.UNKNOWN
        )

    with pytest.deprecated_call(
        match="Checking enum value by original name 'TYPE_UNKNOWN'"
    ):
        assert "TYPE_UNKNOWN" in betterosi.MovingObject.Type

    with pytest.deprecated_call(
        match="Checking enum value by original name 'SUBTYPE_UNKNOWN'"
    ):
        assert "SUBTYPE_UNKNOWN" in betterosi.MovingObject.Type


def test_enum_len_iter_call_repr():
    assert len(betterosi.MovingObjectType) == len(betterosi.MovingObject.Type)
    members = list(betterosi.MovingObjectType)
    assert betterosi.MovingObject.Type.UNKNOWN in members
    assert betterosi.MovingObjectType(0) == betterosi.MovingObject.Type.UNKNOWN
    assert "EnumWrapper" in repr(betterosi.MovingObjectType)


def test_parse_from_string_warning():
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        )
    )
    data = gt.to_binary()

    with pytest.deprecated_call(
        match=r"GroundTruth\.ParseFromString is deprecated\. Use GroundTruth\.from_binary\(\) instead\."
    ):
        parsed = betterosi.GroundTruth.ParseFromString(data)
    assert parsed.version.version_major == 3

    # Also test on instance
    with pytest.deprecated_call(match=r"GroundTruth\.ParseFromString is deprecated"):
        parsed2 = gt.ParseFromString(data)
    assert parsed2.version.version_major == 3


def test_parse_warning():
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        )
    )
    data = gt.to_binary()

    with pytest.deprecated_call(
        match=r"GroundTruth\.parse is deprecated\. Use GroundTruth\.from_binary\(\) instead\."
    ):
        parsed = betterosi.GroundTruth.parse(data)
    assert parsed.version.version_major == 3

    # Also test on instance
    with pytest.deprecated_call(match=r"GroundTruth\.parse is deprecated"):
        parsed2 = gt.parse(data)
    assert parsed2.version.version_major == 3


def test_bytes_message_warning():
    gt = betterosi.GroundTruth(
        timestamp=betterosi.Timestamp(seconds=42, nanos=100),
        moving_object=[betterosi.MovingObject(id=betterosi.Identifier(value=7))],
    )
    with pytest.deprecated_call(
        match=r"bytes\(GroundTruth\) is deprecated\. Use GroundTruth\.to_binary\(\) instead\."
    ):
        data = bytes(gt)
    assert isinstance(data, bytes)
    assert data == gt.to_binary()
    assert len(data) > 0

    # Verify that deserializing bytes(gt) works correctly
    parsed = betterosi.GroundTruth.from_binary(data)
    assert parsed.timestamp.seconds == 42
    assert parsed.moving_object[0].id.value == 7


def test_capitalized_alias_warning():
    with pytest.deprecated_call(
        match=r"'Vector3D' is deprecated\. Use 'Vector3d' instead\."
    ):
        v3d_cls = betterosi.Vector3D
    assert v3d_cls is betterosi.Vector3d

    with pytest.deprecated_call(
        match=r"'Dimension3D' is deprecated\. Use 'Dimension3d' instead\."
    ):
        dim_cls = betterosi.Dimension3D
    assert dim_cls is betterosi.Dimension3d

    with pytest.deprecated_call(
        match=r"'Orientation3D' is deprecated\. Use 'Orientation3d' instead\."
    ):
        orient_cls = betterosi.Orientation3D
    assert orient_cls is betterosi.Orientation3d

    with pytest.deprecated_call(
        match=r"'ColorCmyk' is deprecated\. Use 'ColorCMYK' instead\."
    ):
        cmyk_cls = betterosi.ColorCmyk
    assert cmyk_cls is betterosi.ColorCMYK


def test_nested_message_alias_warning():
    with pytest.deprecated_call(
        match=r"'MovingObjectVehicleClassification' is deprecated\. Use 'MovingObject\.VehicleClassification' instead\."
    ):
        cls = betterosi.MovingObjectVehicleClassification
    assert cls is betterosi.MovingObject.VehicleClassification


def test_enum_wrapper_attr_warning():
    with pytest.deprecated_call(match=r"'EnumWrapper' is deprecated\."):
        cls = betterosi.EnumWrapper
    assert cls is dep.EnumWrapper


def test_top_level_alias_warning_stacklevel():
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always", DeprecationWarning)
        _ = betterosi.Vector3D
        _ = betterosi.LaneClassification
    assert len(recorded) == 2
    for w in recorded:
        assert w.filename == __file__


def test_attribute_error_for_unknown():
    with pytest.raises(
        AttributeError, match="module 'betterosi' has no attribute 'TotallyFakeAttr'"
    ):
        _ = betterosi.TotallyFakeAttr

    with pytest.raises(AttributeError):
        _ = betterosi.MovingObjectType.TotallyFakeAttr


def test_dir_includes_deprecated():
    d = dir(betterosi)
    assert "Vector3D" in d
    assert "MovingObjectVehicleClassification" in d
    assert "EnumWrapper" in d


def test_callable_deprecation_module():
    # Calling module or setup directly
    dep()
    dep.setup()
