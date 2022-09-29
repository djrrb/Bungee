from __future__ import annotations

from enum import IntEnum
from functools import partial
from typing import Any, Callable, List, Mapping, Optional, Sequence, TypeVar

import attr
from attr import define, field
from fontTools.ufoLib import UFOReader

from ufoLib2.objects.guideline import Guideline
from ufoLib2.objects.misc import AttrDictMixin

from .woff import (
    WoffMetadataCopyright,
    WoffMetadataCredit,
    WoffMetadataCredits,
    WoffMetadataDescription,
    WoffMetadataExtension,
    WoffMetadataExtensionItem,
    WoffMetadataExtensionName,
    WoffMetadataExtensionValue,
    WoffMetadataLicense,
    WoffMetadataLicensee,
    WoffMetadataText,
    WoffMetadataTrademark,
    WoffMetadataUniqueID,
    WoffMetadataVendor,
)

__all__ = (
    "Info",
    "GaspRangeRecord",
    "NameRecord",
    "WidthClass",
    "WoffMetadataCopyright",
    "WoffMetadataCredit",
    "WoffMetadataCredits",
    "WoffMetadataDescription",
    "WoffMetadataExtension",
    "WoffMetadataExtensionItem",
    "WoffMetadataExtensionName",
    "WoffMetadataExtensionValue",
    "WoffMetadataLicense",
    "WoffMetadataLicensee",
    "WoffMetadataText",
    "WoffMetadataTrademark",
    "WoffMetadataUniqueID",
    "WoffMetadataVendor",
)


def _positive(instance: Any, attribute: Any, value: int) -> None:
    if value < 0:
        raise ValueError(
            "'{name}' must be at least 0 (got {value!r})".format(
                name=attribute.name, value=value
            )
        )


_optional_positive = attr.validators.optional(_positive)


# or maybe use IntFlag?
class GaspBehavior(IntEnum):
    GRIDFIT = 0
    DOGRAY = 1
    SYMMETRIC_GRIDFIT = 2
    SYMMETRIC_SMOOTHING = 3


def _convert_GaspBehavior(seq: Sequence[GaspBehavior | int]) -> list[GaspBehavior]:
    return [v if isinstance(v, GaspBehavior) else GaspBehavior(v) for v in seq]


@define
class GaspRangeRecord(AttrDictMixin):
    rangeMaxPPEM: int = field(validator=_positive)
    # Use Set[GaspBehavior] instead of List?
    rangeGaspBehavior: List[GaspBehavior] = field(converter=_convert_GaspBehavior)


@define
class NameRecord(AttrDictMixin):
    nameID: int = field(validator=_positive)
    platformID: int = field(validator=_positive)
    encodingID: int = field(validator=_positive)
    languageID: int = field(validator=_positive)
    string: str = ""


class WidthClass(IntEnum):
    ULTRA_CONDENSED = 1
    EXTRA_CONDESED = 2
    CONDENSED = 3
    SEMI_CONDENSED = 4
    NORMAL = 5  # alias for WidthClass.MEDIUM
    MEDIUM = 5
    SEMI_EXPANDED = 6
    EXPANDED = 7
    EXTRA_EXPANDED = 8
    ULTRA_EXPANDED = 9


Tc = TypeVar("Tc", bound=AttrDictMixin)


def _convert_optional_list_of_dicts(
    cls: type[Tc], lst: Sequence[Tc | Mapping[str, Any]] | None
) -> list[Tc] | None:
    if lst is None:
        return None
    return [cls.coerce_from_dict(d) for d in lst]


def _convert_guidelines(
    values: Sequence[Guideline | Mapping[str, Any]] | None,
) -> list[Guideline] | None:
    return _convert_optional_list_of_dicts(Guideline, values)


def _convert_gasp_range_records(
    values: Sequence[GaspRangeRecord | Mapping[str, Any]] | None,
) -> list[GaspRangeRecord] | None:
    return _convert_optional_list_of_dicts(GaspRangeRecord, values)


def _convert_name_records(
    values: Sequence[NameRecord | Mapping[str, Any]] | None,
) -> list[NameRecord] | None:
    return _convert_optional_list_of_dicts(NameRecord, values)


def _convert_WidthClass(value: int | None) -> WidthClass | None:
    return None if value is None else WidthClass(value)


def _convert_WoffMetadataExtensions(
    values: Sequence[WoffMetadataExtension | Mapping[str, Any]] | None
) -> list[WoffMetadataExtension] | None:
    return _convert_optional_list_of_dicts(WoffMetadataExtension, values)


def _converter_setter_property(
    cls: type[Any], converter: Callable[[Any], Any], name: str | None = None
) -> Any:
    if name is None:
        class_name = cls.__name__
        # lower the first char of class name and prepend underscore
        name = f"_{class_name[0].lower()}{class_name[1:]}"
    attr_name: str = name

    def getter(self: Any) -> Any:
        return getattr(self, attr_name)

    def setter(self: Any, value: Any) -> None:
        setattr(self, attr_name, converter(value))

    return property(getter, setter)


def _dict_setter_property(cls: type[Tc], name: str | None = None) -> Any:
    return _converter_setter_property(cls, cls.coerce_from_optional_dict, name)


def _dict_list_setter_property(cls: type[Tc], name: str | None = None) -> Any:
    return _converter_setter_property(
        cls, partial(_convert_optional_list_of_dicts, cls), name
    )


@define
class Info:
    """A data class representing the contents of fontinfo.plist.

    The attributes are formally specified at
    http://unifiedfontobject.org/versions/ufo3/fontinfo.plist/. Value validation is
    mostly done during saving and loading.
    """

    familyName: Optional[str] = None
    styleName: Optional[str] = None
    styleMapFamilyName: Optional[str] = None
    styleMapStyleName: Optional[str] = None
    versionMajor: Optional[int] = field(default=None, validator=_optional_positive)
    versionMinor: Optional[int] = field(default=None, validator=_optional_positive)

    copyright: Optional[str] = None
    trademark: Optional[str] = None

    unitsPerEm: Optional[float] = field(default=None, validator=_optional_positive)
    descender: Optional[float] = None
    xHeight: Optional[float] = None
    capHeight: Optional[float] = None
    ascender: Optional[float] = None
    italicAngle: Optional[float] = None

    note: Optional[str] = None

    _guidelines: Optional[List[Guideline]] = field(
        default=None, converter=_convert_guidelines
    )

    @property
    def guidelines(self) -> list[Guideline] | None:
        return self._guidelines

    @guidelines.setter
    def guidelines(self, value: list[Guideline] | None) -> None:
        self._guidelines = _convert_guidelines(value)

    _openTypeGaspRangeRecords: Optional[List[GaspRangeRecord]] = field(
        default=None, converter=_convert_gasp_range_records
    )

    @property
    def openTypeGaspRangeRecords(self) -> list[GaspRangeRecord] | None:
        return self._openTypeGaspRangeRecords

    @openTypeGaspRangeRecords.setter
    def openTypeGaspRangeRecords(self, value: list[GaspRangeRecord] | None) -> None:
        self._openTypeGaspRangeRecords = _convert_gasp_range_records(value)

    openTypeHeadCreated: Optional[str] = None
    openTypeHeadLowestRecPPEM: Optional[int] = field(
        default=None, validator=_optional_positive
    )
    openTypeHeadFlags: Optional[List[int]] = None

    openTypeHheaAscender: Optional[int] = None
    openTypeHheaDescender: Optional[int] = None
    openTypeHheaLineGap: Optional[int] = None
    openTypeHheaCaretSlopeRise: Optional[int] = None
    openTypeHheaCaretSlopeRun: Optional[int] = None
    openTypeHheaCaretOffset: Optional[int] = None

    openTypeNameDesigner: Optional[str] = None
    openTypeNameDesignerURL: Optional[str] = None
    openTypeNameManufacturer: Optional[str] = None
    openTypeNameManufacturerURL: Optional[str] = None
    openTypeNameLicense: Optional[str] = None
    openTypeNameLicenseURL: Optional[str] = None
    openTypeNameVersion: Optional[str] = None
    openTypeNameUniqueID: Optional[str] = None
    openTypeNameDescription: Optional[str] = None
    openTypeNamePreferredFamilyName: Optional[str] = None
    openTypeNamePreferredSubfamilyName: Optional[str] = None
    openTypeNameCompatibleFullName: Optional[str] = None
    openTypeNameSampleText: Optional[str] = None
    openTypeNameWWSFamilyName: Optional[str] = None
    openTypeNameWWSSubfamilyName: Optional[str] = None

    _openTypeNameRecords: Optional[List[NameRecord]] = field(
        default=None, converter=_convert_name_records
    )

    @property
    def openTypeNameRecords(self) -> list[NameRecord] | None:
        return self._openTypeNameRecords

    @openTypeNameRecords.setter
    def openTypeNameRecords(self, value: list[NameRecord] | None) -> None:
        self._openTypeNameRecords = _convert_name_records(value)

    _openTypeOS2WidthClass: Optional[WidthClass] = field(
        default=None, converter=_convert_WidthClass
    )

    @property
    def openTypeOS2WidthClass(self) -> WidthClass | None:
        return self._openTypeOS2WidthClass

    @openTypeOS2WidthClass.setter
    def openTypeOS2WidthClass(self, value: WidthClass | None) -> None:
        self._openTypeOS2WidthClass = value if value is None else WidthClass(value)

    openTypeOS2WeightClass: Optional[int] = field(default=None)

    @openTypeOS2WeightClass.validator
    def _validate_weight_class(self, attribute: Any, value: int | None) -> None:
        if value is not None and (value < 1 or value > 1000):
            raise ValueError("'openTypeOS2WeightClass' must be between 1 and 1000")

    openTypeOS2Selection: Optional[List[int]] = None
    openTypeOS2VendorID: Optional[str] = None
    openTypeOS2Panose: Optional[List[int]] = None
    openTypeOS2FamilyClass: Optional[List[int]] = None
    openTypeOS2UnicodeRanges: Optional[List[int]] = None
    openTypeOS2CodePageRanges: Optional[List[int]] = None
    openTypeOS2TypoAscender: Optional[int] = None
    openTypeOS2TypoDescender: Optional[int] = None
    openTypeOS2TypoLineGap: Optional[int] = None
    openTypeOS2WinAscent: Optional[int] = field(
        default=None, validator=_optional_positive
    )
    openTypeOS2WinDescent: Optional[int] = field(
        default=None, validator=_optional_positive
    )
    openTypeOS2Type: Optional[List[int]] = None
    openTypeOS2SubscriptXSize: Optional[int] = None
    openTypeOS2SubscriptYSize: Optional[int] = None
    openTypeOS2SubscriptXOffset: Optional[int] = None
    openTypeOS2SubscriptYOffset: Optional[int] = None
    openTypeOS2SuperscriptXSize: Optional[int] = None
    openTypeOS2SuperscriptYSize: Optional[int] = None
    openTypeOS2SuperscriptXOffset: Optional[int] = None
    openTypeOS2SuperscriptYOffset: Optional[int] = None
    openTypeOS2StrikeoutSize: Optional[int] = None
    openTypeOS2StrikeoutPosition: Optional[int] = None

    openTypeVheaVertTypoAscender: Optional[int] = None
    openTypeVheaVertTypoDescender: Optional[int] = None
    openTypeVheaVertTypoLineGap: Optional[int] = None
    openTypeVheaCaretSlopeRise: Optional[int] = None
    openTypeVheaCaretSlopeRun: Optional[int] = None
    openTypeVheaCaretOffset: Optional[int] = None

    postscriptFontName: Optional[str] = None
    postscriptFullName: Optional[str] = None
    postscriptSlantAngle: Optional[float] = None
    postscriptUniqueID: Optional[int] = None
    postscriptUnderlineThickness: Optional[float] = None
    postscriptUnderlinePosition: Optional[float] = None
    postscriptIsFixedPitch: Optional[bool] = None
    postscriptBlueValues: Optional[List[float]] = None
    postscriptOtherBlues: Optional[List[float]] = None
    postscriptFamilyBlues: Optional[List[float]] = None
    postscriptFamilyOtherBlues: Optional[List[float]] = None
    postscriptStemSnapH: Optional[List[float]] = None
    postscriptStemSnapV: Optional[List[float]] = None
    postscriptBlueFuzz: Optional[float] = None
    postscriptBlueShift: Optional[float] = None
    postscriptBlueScale: Optional[float] = None
    postscriptForceBold: Optional[bool] = None
    postscriptDefaultWidthX: Optional[float] = None
    postscriptNominalWidthX: Optional[float] = None
    postscriptWeightName: Optional[str] = None
    postscriptDefaultCharacter: Optional[str] = None
    postscriptWindowsCharacterSet: Optional[int] = None

    # old stuff
    macintoshFONDName: Optional[str] = None
    macintoshFONDFamilyID: Optional[int] = None
    year: Optional[int] = None

    # woff metadata
    woffMajorVersion: Optional[int] = field(default=None, validator=_optional_positive)
    woffMinorVersion: Optional[int] = field(default=None, validator=_optional_positive)
    _woffMetadataUniqueID: Optional[WoffMetadataUniqueID] = field(
        default=None,
        # mute mypy error "unsupported converter, only named functions and types ..."
        # The woff metadata attributes are too many to bother defining named
        # converters and properties. Maybe one day...
        converter=WoffMetadataUniqueID.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataUniqueID = _dict_setter_property(WoffMetadataUniqueID)

    _woffMetadataVendor: Optional[WoffMetadataVendor] = field(
        default=None,
        converter=WoffMetadataVendor.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataVendor = _dict_setter_property(WoffMetadataVendor)

    _woffMetadataCredits: Optional[WoffMetadataCredits] = field(
        default=None,
        converter=WoffMetadataCredits.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataCredits = _dict_setter_property(WoffMetadataCredits)

    _woffMetadataDescription: Optional[WoffMetadataDescription] = field(
        default=None,
        converter=WoffMetadataDescription.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataDescription = _dict_setter_property(WoffMetadataDescription)

    _woffMetadataLicense: Optional[WoffMetadataLicense] = field(
        default=None,
        converter=WoffMetadataLicense.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataLicense = _dict_setter_property(WoffMetadataLicense)

    _woffMetadataCopyright: Optional[WoffMetadataCopyright] = field(
        default=None,
        converter=WoffMetadataCopyright.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataCopyright = _dict_setter_property(WoffMetadataCopyright)

    _woffMetadataTrademark: Optional[WoffMetadataTrademark] = field(
        default=None,
        converter=WoffMetadataTrademark.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataTrademark = _dict_setter_property(WoffMetadataTrademark)

    _woffMetadataLicensee: Optional[WoffMetadataLicensee] = field(
        default=None,
        converter=WoffMetadataLicensee.coerce_from_optional_dict,  # type: ignore
    )
    woffMetadataLicensee = _dict_setter_property(WoffMetadataLicensee)

    _woffMetadataExtensions: Optional[List[WoffMetadataExtension]] = field(
        default=None,
        converter=_convert_WoffMetadataExtensions,
    )
    woffMetadataExtensions = _dict_list_setter_property(
        WoffMetadataExtension, "_woffMetadataExtensions"
    )

    @classmethod
    def read(cls, reader: UFOReader) -> Info:
        """Instantiates a Info object from a
        :class:`fontTools.ufoLib.UFOReader`."""
        self = cls()
        reader.readInfo(self)
        return self
