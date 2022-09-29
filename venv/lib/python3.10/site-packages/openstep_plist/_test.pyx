#cython: language_level=3
#distutils: define_macros=CYTHON_TRACE_NOGIL=1

from .parser cimport (
    ParseInfo,
    line_number_strings as _line_number_strings,
    advance_to_non_space as _advance_to_non_space,
    get_slashed_char as _get_slashed_char,
    parse_unquoted_plist_string as _parse_unquoted_plist_string,
    parse_plist_string as _parse_plist_string,
)
from .util cimport (
    PY_NARROW_UNICODE,
    tounicode,
    is_valid_unquoted_string_char as _is_valid_unquoted_string_char,
)
from .writer cimport string_needs_quotes as _string_needs_quotes
from cpython.unicode cimport (
    PyUnicode_FromUnicode, PyUnicode_AS_UNICODE, PyUnicode_GET_SIZE,
)


cdef class ParseContext:

    cdef unicode s
    cdef ParseInfo pi
    cdef object dict_type

    @classmethod
    def fromstring(
            ParseContext cls,
            string,
            Py_ssize_t offset=0,
            dict_type=dict,
            bint use_numbers=False
    ):
        cdef ParseContext self = ParseContext.__new__(cls)
        self.s = tounicode(string)
        cdef Py_ssize_t length = PyUnicode_GET_SIZE(self.s)
        cdef Py_UNICODE* buf = PyUnicode_AS_UNICODE(self.s)
        self.dict_type = dict_type
        self.pi = ParseInfo(
            begin=buf,
            curr=buf + offset,
            end=buf + length,
            dict_type=<void*>dict_type,
            use_numbers=use_numbers,
        )
        return self


def is_narrow_unicode():
    return PY_NARROW_UNICODE


def is_valid_unquoted_string_char(Py_UNICODE c):
    return _is_valid_unquoted_string_char(c)


def line_number_strings(s, offset=0):
    cdef ParseContext ctx = ParseContext.fromstring(s, offset)
    return _line_number_strings(&ctx.pi)


def advance_to_non_space(s, offset=0):
    cdef ParseContext ctx = ParseContext.fromstring(s, offset)
    eof = not _advance_to_non_space(&ctx.pi)
    return None if eof else s[ctx.pi.curr - ctx.pi.begin]


def get_slashed_char(s, offset=0):
    cdef ParseContext ctx = ParseContext.fromstring(s, offset)
    return _get_slashed_char(&ctx.pi)


def parse_unquoted_plist_string(s):
    cdef ParseContext ctx = ParseContext.fromstring(s)
    return _parse_unquoted_plist_string(&ctx.pi)


def parse_plist_string(s, required=True):
    cdef ParseContext ctx = ParseContext.fromstring(s)
    return _parse_plist_string(&ctx.pi, required=required)


def string_needs_quotes(s):
    cdef ParseContext ctx = ParseContext.fromstring(s)
    return _string_needs_quotes(ctx.pi.begin, len(s))
