"""Fontinfo.plist fields for WOFF 1.0 metadata.

https://unifiedfontobject.org/versions/ufo3/fontinfo.plist/#woff-data
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Type, TypeVar

from attr import Attribute, define, field

from ufoLib2.objects.misc import AttrDictMixin

_T = TypeVar("_T", bound=AttrDictMixin)


def _convert_list_of_woff_metadata(
    cls: Type[_T], values: Sequence[_T | Mapping[str, Any]]
) -> list[_T]:
    return [cls.coerce_from_dict(v) for v in values]


@define
class WoffMetadataUniqueID(AttrDictMixin):
    id: str


@define
class WoffMetadataVendor(AttrDictMixin):
    name: str
    url: Optional[str] = None
    dir: Optional[str] = None
    # 'class' of course is reserved in Python
    class_: Optional[str] = field(default=None, metadata={"rename_attr": "class"})


@define
class WoffMetadataCredit(AttrDictMixin):
    name: str
    url: Optional[str] = None
    role: Optional[str] = None
    dir: Optional[str] = None
    class_: Optional[str] = field(default=None, metadata={"rename_attr": "class"})


def _convert_list_of_woff_metadata_credits(
    value: list[WoffMetadataCredit | Mapping[str, Any]],
) -> list[WoffMetadataCredit]:
    return _convert_list_of_woff_metadata(WoffMetadataCredit, value)


@define
class WoffMetadataCredits(AttrDictMixin):
    credits: List[WoffMetadataCredit] = field(
        factory=list,
        converter=_convert_list_of_woff_metadata_credits,
    )


@define
class WoffMetadataText(AttrDictMixin):
    text: str
    language: Optional[str] = None
    dir: Optional[str] = None
    class_: Optional[str] = field(default=None, metadata={"rename_attr": "class"})


def _at_least_one_item(
    self: Any, attribute: Attribute[Any], value: Sequence[Any]
) -> None:
    if len(value) == 0:
        raise ValueError(
            f"{self.__class__.__name__}.{attribute.name} must contain at list 1 item"
        )


def _convert_list_of_woff_metadata_texts(
    value: list[WoffMetadataText | Mapping[str, Any]],
) -> list[WoffMetadataText]:
    return _convert_list_of_woff_metadata(WoffMetadataText, value)


@define
class WoffMetadataDescription(AttrDictMixin):
    url: Optional[str] = None
    text: List[WoffMetadataText] = field(
        factory=list,
        validator=_at_least_one_item,
        converter=_convert_list_of_woff_metadata_texts,
    )


@define
class WoffMetadataLicense(AttrDictMixin):
    url: Optional[str] = None
    id: Optional[str] = None
    text: List[WoffMetadataText] = field(
        factory=list,
        converter=_convert_list_of_woff_metadata_texts,
    )


@define
class WoffMetadataCopyright(AttrDictMixin):
    text: List[WoffMetadataText] = field(
        factory=list,
        validator=_at_least_one_item,
        converter=_convert_list_of_woff_metadata_texts,
    )


@define
class WoffMetadataTrademark(AttrDictMixin):
    text: List[WoffMetadataText] = field(
        factory=list,
        validator=_at_least_one_item,
        converter=_convert_list_of_woff_metadata_texts,
    )


@define
class WoffMetadataLicensee(AttrDictMixin):
    name: str
    dir: Optional[str] = None
    class_: Optional[str] = field(default=None, metadata={"rename_attr": "class"})


@define
class WoffMetadataExtensionName(AttrDictMixin):
    text: str
    language: Optional[str] = None
    dir: Optional[str] = None
    class_: Optional[str] = field(default=None, metadata={"rename_attr": "class"})


@define
class WoffMetadataExtensionValue(AttrDictMixin):
    text: str
    language: Optional[str] = None
    dir: Optional[str] = None
    class_: Optional[str] = field(default=None, metadata={"rename_attr": "class"})


def _convert_list_of_woff_metadata_extension_name(
    value: list[WoffMetadataExtensionName | Mapping[str, Any]],
) -> list[WoffMetadataExtensionName]:
    return _convert_list_of_woff_metadata(WoffMetadataExtensionName, value)


def _convert_list_of_woff_metadata_extension_value(
    value: list[WoffMetadataExtensionValue | Mapping[str, Any]],
) -> list[WoffMetadataExtensionValue]:
    return _convert_list_of_woff_metadata(WoffMetadataExtensionValue, value)


@define
class WoffMetadataExtensionItem(AttrDictMixin):
    id: Optional[str] = None
    names: List[WoffMetadataExtensionName] = field(
        factory=list,
        validator=_at_least_one_item,
        converter=_convert_list_of_woff_metadata_extension_name,
    )
    # 'values()' is the name of the dict method, hence the attribute named 'values_'
    values_: List[WoffMetadataExtensionValue] = field(
        factory=list,
        validator=_at_least_one_item,
        converter=_convert_list_of_woff_metadata_extension_value,
        metadata={"rename_attr": "values"},
    )


def _convert_list_of_woff_metadata_extension_item(
    value: list[WoffMetadataExtensionItem | Mapping[str, Any]],
) -> list[WoffMetadataExtensionItem]:
    return _convert_list_of_woff_metadata(WoffMetadataExtensionItem, value)


@define
class WoffMetadataExtension(AttrDictMixin):
    id: Optional[str]
    names: List[WoffMetadataExtensionName] = field(
        factory=list,
        converter=_convert_list_of_woff_metadata_extension_name,
    )
    # 'items()' is the name of the dict method, hence the attribute named 'items_'
    items_: List[WoffMetadataExtensionItem] = field(
        factory=list,
        validator=_at_least_one_item,
        converter=_convert_list_of_woff_metadata_extension_item,
        metadata={"rename_attr": "items"},
    )
