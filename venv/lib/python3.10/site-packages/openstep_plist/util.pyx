#cython: language_level=3
#distutils: define_macros=CYTHON_TRACE_NOGIL=1

from cpython.version cimport PY_MAJOR_VERSION
from libc.stdint cimport uint16_t, uint32_t
import sys


cdef inline unicode tounicode(s, encoding="ascii", errors="strict"):
    if type(s) is unicode:
        return <unicode>s
    elif PY_MAJOR_VERSION < 3 and isinstance(s, bytes):
        return (<bytes>s).decode(encoding, errors=errors)
    elif isinstance(s, unicode):
        return unicode(s)
    else:
        raise TypeError(f"Could not convert to unicode: {s!r}")


cdef inline object tostr(s, encoding="ascii", errors="strict"):
    if isinstance(s, bytes):
        return s if PY_MAJOR_VERSION < 3 else s.decode(encoding, errors=errors)
    elif isinstance(s, unicode):
        return s.encode(encoding, errors=errors) if PY_MAJOR_VERSION < 3 else s
    else:
        raise TypeError(f"Could not convert to str: {s!r}")


cdef inline bint is_valid_unquoted_string_char(Py_UNICODE x):
    return (
        (x >= c'a' and x <= c'z') or
        (x >= c'A' and x <= c'Z') or
        (x >= c'0' and x <= c'9') or
        x == c'_' or
        x == c'$' or
        x == c'/' or
        x == c':' or
        x == c'.' or
        x == c'-'
    )


cdef bint PY_NARROW_UNICODE = sizeof(Py_UNICODE) != 4


cdef inline bint is_high_surrogate(uint32_t ch):
    return ch >= 0xD800 and ch <= 0xDBFF


cdef inline bint is_low_surrogate(uint32_t ch):
    return ch >= 0xDC00 and ch <= 0xDFFF


cdef inline uint32_t unicode_scalar_from_surrogates(uint16_t high, uint16_t low):
    return (high - 0xD800) * 0x400 + low - 0xDC00 + 0x10000


cdef inline uint16_t high_surrogate_from_unicode_scalar(uint32_t scalar):
    return ((scalar - 0x10000) // 0x400) + 0xD800


cdef inline uint16_t low_surrogate_from_unicode_scalar(uint32_t scalar):
    return (scalar - 0x10000) % 0x400 + 0xDC00
