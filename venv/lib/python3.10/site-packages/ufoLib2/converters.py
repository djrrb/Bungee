from __future__ import annotations

import sys
from functools import partial
from typing import Any, Callable, Tuple, Type, cast

from attr import fields, has, resolve_types
from cattr import GenConverter
from cattr.gen import (
    AttributeOverride,
    make_dict_structure_fn,
    make_dict_unstructure_fn,
    override,
)
from fontTools.misc.transform import Transform

is_py37 = sys.version_info[:2] == (3, 7)

if is_py37:

    def get_origin(cl: Type[Any]) -> Any:
        return getattr(cl, "__origin__", None)

else:
    from typing import get_origin  # type: ignore


__all__ = [
    "register_hooks",
    "structure",
    "unstructure",
]


def is_ufoLib2_class(cls: Type[Any]) -> bool:
    mod: str = getattr(cls, "__module__", "")
    return mod.split(".")[0] == "ufoLib2"


def is_ufoLib2_attrs_class(cls: Type[Any]) -> bool:
    return is_ufoLib2_class(cls) and (has(cls) or has(get_origin(cls)))


def is_ufoLib2_class_with_custom_unstructure(cls: Type[Any]) -> bool:
    return is_ufoLib2_class(cls) and hasattr(cls, "_unstructure")


def is_ufoLib2_class_with_custom_structure(cls: Type[Any]) -> bool:
    return is_ufoLib2_class(cls) and hasattr(cls, "_structure")


def register_hooks(conv: GenConverter, allow_bytes: bool = True) -> None:
    def attrs_hook_factory(
        cls: Type[Any], gen_fn: Callable[..., Callable[[Any], Any]], structuring: bool
    ) -> Callable[[Any], Any]:
        base = get_origin(cls)
        if base is None:
            base = cls
        attribs = fields(base)
        # PEP563 postponed annotations need resolving as we check Attribute.type below
        resolve_types(base)
        kwargs: dict[str, bool | AttributeOverride] = {}
        if structuring:
            kwargs["_cattrs_forbid_extra_keys"] = conv.forbid_extra_keys
            kwargs["_cattrs_prefer_attrib_converters"] = conv._prefer_attrib_converters
        else:
            kwargs["_cattrs_omit_if_default"] = conv.omit_if_default
        for a in attribs:
            if a.type in conv.type_overrides:
                # cattrs' gen_(un)structure_attrs_fromdict (used by default for attrs
                # classes that don't have a custom hook registered) check for any
                # type_overrides (Dict[Type, AttributeOverride]); they allow a custom
                # converter to omit specific attributes of given type e.g.:
                # >>> conv = GenConverter(type_overrides={Image: override(omit=True)})
                attrib_override = conv.type_overrides[a.type]
            else:
                # by default, we omit all Optional attributes (i.e. with None default),
                # overriding a Converter's global 'omit_if_default' option. Specific
                # attibutes can still define their own 'omit_if_default' behavior in
                # the Attribute.metadata dict.
                attrib_override = override(
                    omit_if_default=a.metadata.get(
                        "omit_if_default", a.default is None or None
                    ),
                    rename=a.metadata.get(
                        "rename_attr", a.name[1:] if a.name[0] == "_" else None
                    ),
                    omit=not a.init,
                )
            kwargs[a.name] = attrib_override

        return gen_fn(cls, conv, **kwargs)

    def custom_unstructure_hook_factory(cls: Type[Any]) -> Callable[[Any], Any]:
        return partial(cls._unstructure, converter=conv)

    def custom_structure_hook_factory(cls: Type[Any]) -> Callable[[Any], Any]:
        return partial(cls._structure, converter=conv)

    def unstructure_transform(t: Transform) -> Tuple[float]:
        return cast(Tuple[float], tuple(t))

    conv.register_unstructure_hook_factory(
        is_ufoLib2_attrs_class,
        partial(attrs_hook_factory, gen_fn=make_dict_unstructure_fn, structuring=False),
    )
    conv.register_unstructure_hook_factory(
        is_ufoLib2_class_with_custom_unstructure,
        custom_unstructure_hook_factory,
    )
    conv.register_unstructure_hook(
        cast(Type[Transform], Transform), unstructure_transform
    )

    conv.register_structure_hook_factory(
        is_ufoLib2_attrs_class,
        partial(attrs_hook_factory, gen_fn=make_dict_structure_fn, structuring=True),
    )
    conv.register_structure_hook_factory(
        is_ufoLib2_class_with_custom_structure,
        custom_structure_hook_factory,
    )

    if not allow_bytes:
        from base64 import b64decode, b64encode

        def unstructure_bytes(v: bytes) -> str:
            return (b64encode(v) if v else b"").decode("utf8")

        def structure_bytes(v: str, _: Any) -> bytes:
            return b64decode(v)

        conv.register_unstructure_hook(bytes, unstructure_bytes)
        conv.register_structure_hook(bytes, structure_bytes)


default_converter = GenConverter(
    omit_if_default=True,
    forbid_extra_keys=True,
    prefer_attrib_converters=False,
)
register_hooks(default_converter, allow_bytes=False)

structure = default_converter.structure
unstructure = default_converter.unstructure
