#cython: language_level=3


cdef bint string_needs_quotes(const Py_UNICODE *a, Py_ssize_t length)
