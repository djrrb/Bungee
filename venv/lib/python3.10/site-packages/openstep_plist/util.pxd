#cython: language_level=3

from libc.stdint cimport uint16_t, uint32_t


cdef extern from "<ctype.h>":
    int isxdigit(int c)
    int isdigit(int c)
    int isprint(int c)


cdef unicode tounicode(s, encoding=*, errors=*)


cdef tostr(s, encoding=*, errors=*)


cdef bint is_valid_unquoted_string_char(Py_UNICODE x)


cdef bint PY_NARROW_UNICODE


cdef bint is_high_surrogate(uint32_t ch)


cdef bint is_low_surrogate(uint32_t ch)


cdef uint32_t unicode_scalar_from_surrogates(uint16_t high, uint16_t low)


cdef uint16_t high_surrogate_from_unicode_scalar(uint32_t scalar)


cdef uint16_t low_surrogate_from_unicode_scalar(uint32_t scalar)
