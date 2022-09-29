#cython: language_level=3
#distutils: define_macros=CYTHON_TRACE_NOGIL=1

from cpython.bytes cimport PyBytes_FromStringAndSize
from cpython.unicode cimport (
    PyUnicode_FromUnicode, PyUnicode_AS_UNICODE, PyUnicode_GET_SIZE,
)
from libc.stdint cimport uint8_t, uint16_t, uint32_t
from libcpp.algorithm cimport copy
from libcpp.iterator cimport back_inserter
from libcpp.vector cimport vector
from cpython.version cimport PY_MAJOR_VERSION
cimport cython

from .util cimport (
    tounicode,
    tostr,
    is_valid_unquoted_string_char,
    isdigit,
    isxdigit,
    PY_NARROW_UNICODE,
    is_high_surrogate,
    is_low_surrogate,
    unicode_scalar_from_surrogates,
)


cdef uint32_t line_number_strings(ParseInfo *pi):
    # warning: doesn't have a good idea of Unicode line separators
    cdef const Py_UNICODE *p = pi.begin
    cdef uint32_t count = 1
    while p < pi.curr:
        if p[0] == c'\r':
            count += 1
            if (p + 1)[0] == c'\n':
                p += 1
        elif p[0] == c'\n':
            count += 1
        p += 1
    return count


cdef bint advance_to_non_space(ParseInfo *pi):
    """Returns true if the advance found something that's not whitespace
    before the end of the buffer, false otherwise.
    """
    cdef Py_UNICODE ch2, ch3
    while pi.curr < pi.end:
        ch2 = pi.curr[0]
        pi.curr += 1
        if ch2 >= 9 and ch2 <= 0x0d:
            # tab, newline, vt, form feed, carriage return
            continue
        elif ch2 == c' ' or ch2 == 0x2028 or ch2 == 0x2029:
            continue
        elif ch2 == c'/':
            if pi.curr >= pi.end:
                # whoops; back up and return
                pi.curr -= 1
                return True
            elif pi.curr[0] == c'/':
                pi.curr += 1
                while pi.curr < pi.end:
                    # go to end of // comment line
                    ch3 = pi.curr[0]
                    if ch3 == c'\n' or ch3 == c'\r' or ch3 == 0x2028 or ch3 == 0x2029:
                        break
                    pi.curr += 1
            elif pi.curr[0] == c'*':
                # handle C-style comments /* ... */
                pi.curr += 1
                while pi.curr < pi.end:
                    ch2 = pi.curr[0]
                    pi.curr += 1
                    if ch2 == c'*' and pi.curr < pi.end and pi.curr[0] == c'/':
                        pi.curr += 1  # advance past the '/'
                        break
            else:
                pi.curr -= 1
                return True
        else:
            pi.curr -= 1
            return True

    return False


# Table mapping from NextStep Encoding to Unicode characters, used
# for decoding octal escaped character codes within quoted plist strings.
# Since the first 128 characters (0x0 - 0x7f) are identical to ASCII
# and Unicode, the table only maps NextStep range from 0x80 - 0xFF.
# Source: ftp://ftp.unicode.org/Public/MAPPINGS/VENDORS/NEXT/NEXTSTEP.TXT
cdef unsigned short* NEXT_STEP_DECODING_TABLE = [
    0xA0, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC7, 0xC8, 0xC9,
    0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF, 0xD0, 0xD1, 0xD2, 0xD3,
    0xD4, 0xD5, 0xD6, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xB5,
    0xD7, 0xF7, 0xA9, 0xA1, 0xA2, 0xA3, 0x2044, 0xA5, 0x192, 0xA7,
    0xA4, 0x2019, 0x201C, 0xAB, 0x2039, 0x203A, 0xFB01, 0xFB02, 0xAE, 0x2013,
    0x2020, 0x2021, 0xB7, 0xA6, 0xB6, 0x2022, 0x201A, 0x201E, 0x201D, 0xBB,
    0x2026, 0x2030, 0xAC, 0xBF, 0xB9, 0x2CB, 0xB4, 0x2C6, 0x2DC, 0xAF,
    0x2D8, 0x2D9, 0xA8, 0xB2, 0x2DA, 0xB8, 0xB3, 0x2DD, 0x2DB, 0x2C7,
    0x2014, 0xB1, 0xBC, 0xBD, 0xBE, 0xE0, 0xE1, 0xE2, 0xE3, 0xE4,
    0xE5, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xC6, 0xED, 0xAA,
    0xEE, 0xEF, 0xF0, 0xF1, 0x141, 0xD8, 0x152, 0xBA, 0xF2, 0xF3,
    0xF4, 0xF5, 0xF6, 0xE6, 0xF9, 0xFA, 0xFB, 0x131, 0xFC, 0xFD,
    0x142, 0xF8, 0x153, 0xDF, 0xFE, 0xFF, 0xFFFD, 0xFFFD,
]


@cython.boundscheck(False)
@cython.wraparound(False)
cdef Py_UNICODE get_slashed_char(ParseInfo *pi):
    cdef Py_UNICODE result
    cdef uint8_t num
    cdef unsigned int codepoint, num_digits
    cdef unsigned long unum
    cdef unsigned long ch = pi.curr[0]

    pi.curr += 1
    if (
        ch == c'0' or
        ch == c'1' or
        ch == c'2' or
        ch == c'3' or
        ch == c'4' or
        ch == c'5' or
        ch == c'6' or
        ch == c'7'
    ):
        num = ch - c'0'
        # three digits maximum to avoid reading \000 followed by 5 as \5 !
        ch = pi.curr[0]
        if ch >= c'0' and ch <= c'7':
            # we use in this test the fact that the buffer is zero-terminated
            pi.curr += 1
            num = (num << 3) + ch - c'0'
            if pi.curr < pi.end:
                ch = pi.curr[0]
                if ch >= c'0' and ch <= c'7':
                    pi.curr += 1
                    num = (num << 3) + ch - c'0'
            if num < 128:  # ascii
                codepoint = num
            else:
                codepoint = NEXT_STEP_DECODING_TABLE[num-128]
            return codepoint
    elif ch == c'U':
        unum = 0
        num_digits = 4
        while pi.curr < pi.end and num_digits > 0:
            ch = pi.curr[0]
            if ch < 128 and isxdigit(<unsigned char>ch):
                pi.curr += 1
                unum = (unum << 4) + (
                    (ch - c'0') if ch <= c'9' else (
                        (ch - c'A' + 10) if ch <= c'F' else (ch - c'a' + 10)
                    )
                )
            num_digits -= 1
        return unum
    elif ch == c'a':
        return c'\a'
    elif ch == c'b':
        return c'\b'
    elif ch == c'f':
        return c'\f'
    elif ch == c'n':
        return c'\n'
    elif ch == c'r':
        return c'\r'
    elif ch == c't':
        return c'\t'
    elif ch == c'v':
        return c'\v'
    elif ch == c'"':
        return c'"'
    elif ch == c'\n':
        return c'\n'

    return ch


cdef unicode parse_quoted_plist_string(ParseInfo *pi, Py_UNICODE quote):
    cdef vector[Py_UNICODE] string
    cdef const Py_UNICODE *start_mark = pi.curr
    cdef const Py_UNICODE *mark = pi.curr
    cdef const Py_UNICODE *tmp
    cdef Py_UNICODE ch, ch2
    while pi.curr < pi.end:
        ch = pi.curr[0]
        if ch == quote:
            break
        elif ch == c'\\':
            string.reserve(string.size() + (pi.curr - mark))
            copy(mark, pi.curr, back_inserter(string))
            pi.curr += 1
            ch = get_slashed_char(pi)
            # If we are NOT on a "narrow" python 2 build, then we need to parse
            # two successive \UXXXX escape sequences as one surrogate pair
            # representing a "supplementary" Unicode scalar value.
            # If we are on a "narrow" build, then the two code units already
            # represent a single codepoint internally.
            if (
                not PY_NARROW_UNICODE and is_high_surrogate(ch)
                and pi.curr < pi.end and pi.curr[0] == c"\\"
            ):
                tmp = pi.curr
                pi.curr += 1
                ch2 = get_slashed_char(pi)
                if is_low_surrogate(ch2):
                    ch = unicode_scalar_from_surrogates(high=ch, low=ch2)
                else:
                    # XXX maybe we should raise here instead of letting this
                    # lone high surrogate (not followed by a low) pass through?
                    pi.curr = tmp
            string.push_back(ch)
            mark = pi.curr
        else:
            pi.curr += 1
    if pi.end <= pi.curr:
        raise ParseError(
            "Unterminated quoted string starting on line %d"
            % line_number_strings(pi)
        )
    if mark != pi.curr:
        string.reserve(string.size() + (pi.curr - mark))
        copy(mark, pi.curr, back_inserter(string))
    # Advance past the quote character before returning
    pi.curr += 1

    return PyUnicode_FromUnicode(<const Py_UNICODE*>string.const_data(), string.size())


def string_to_number(unicode s not None, bint required=True):
    """Convert string s to either int or float.
    Raises ValueError if the string is not a number.
    """
    cdef:
        Py_UNICODE c
        Py_UNICODE* buf
        Py_ssize_t length = PyUnicode_GET_SIZE(s)

    if length:
        buf = PyUnicode_AS_UNICODE(s)
        kind = get_unquoted_string_type(buf, length)
        if kind == UNQUOTED_FLOAT:
            return float(s)
        elif kind == UNQUOTED_INTEGER:
            return int(s)

    if required:
        raise ValueError(f"Could not convert string to float or int: {s!r}")
    else:
        return s


cdef UnquotedType get_unquoted_string_type(
    const Py_UNICODE *buf, Py_ssize_t length
):
    """Check if Py_UNICODE array starts with a digit, or '-' followed
    by a digit, and if it contains a decimal point '.'.
    Return 0 if string cannot contain a number, 1 if it contains an
    integer, and 2 if it contains a float.
    """
    # NOTE: floats in scientific notation (e.g. 1e-5) or starting with a
    # "." (e.g. .05) are not handled here, but are treated as strings.
    cdef:
        bint maybe_number = True
        bint is_float = False
        int i = 0
        # deref here is safe since Py_UNICODE* are NULL-terminated
        Py_UNICODE ch = buf[i]

    if ch == c'-':
        if length > 1:
            i += 1
            ch = buf[i]
            if ch > c'9' or ch < c'0':
                maybe_number = False
        else:
            maybe_number = False
    elif ch > c'9' or ch < c'0':
        maybe_number = False

    if maybe_number:
        for i in range(i, length):
            ch = buf[i]
            if ch > c'9' or ch < c'.' or ch == c'/':
                return UNQUOTED_STRING  # not a number
            elif ch == c'.':
                if not is_float:
                    is_float = True
                else:
                    # seen a second '.', it's not a float
                    return UNQUOTED_STRING

        return UNQUOTED_FLOAT if is_float else UNQUOTED_INTEGER

    return UNQUOTED_STRING


cdef object parse_unquoted_plist_string(ParseInfo *pi, bint ensure_string=False):
    cdef:
        const Py_UNICODE *mark = pi.curr
        Py_UNICODE ch
        Py_ssize_t length, i
        unicode s
        UnquotedType kind

    while pi.curr < pi.end:
        ch = pi.curr[0]
        if is_valid_unquoted_string_char(ch):
            pi.curr += 1
        else:
            break
    if pi.curr != mark:
        length = pi.curr - mark
        s = PyUnicode_FromUnicode(mark, length)

        if not ensure_string and pi.use_numbers:
            kind = get_unquoted_string_type(mark, length)
            if kind == UNQUOTED_FLOAT:
                return float(s)
            elif kind == UNQUOTED_INTEGER:
                return int(s)

        return s

    raise ParseError("Unexpected EOF")


cdef unicode parse_plist_string(ParseInfo *pi, bint required=True):
    cdef Py_UNICODE ch
    if not advance_to_non_space(pi):
        if required:
            raise ParseError("Unexpected EOF while parsing string")
    ch = pi.curr[0]
    if ch == c'\'' or ch == c'"':
        pi.curr += 1
        return parse_quoted_plist_string(pi, ch)
    elif is_valid_unquoted_string_char(ch):
        return parse_unquoted_plist_string(pi, ensure_string=True)
    else:
        if required:
            raise ParseError(
                "Invalid string character at line %d: %r"
                % (line_number_strings(pi), ch)
            )
    return None


cdef list parse_plist_array(ParseInfo *pi):
    cdef list result = []
    cdef object tmp = parse_plist_object(pi, required=False)
    cdef bint found_char
    while tmp is not None:
        result.append(tmp)
        found_char = advance_to_non_space(pi)
        if not found_char:
            raise ParseError(
                "Missing ',' for array at line %d" % line_number_strings(pi)
            )
        if pi.curr[0] != c',':
            tmp = None
        else:
            pi.curr += 1
            tmp = parse_plist_object(pi, required=False)
    found_char = advance_to_non_space(pi)
    if not found_char or pi.curr[0] != c')':
        raise ParseError(
            "Expected terminating ')' for array at line %d" % line_number_strings(pi)
        )
    pi.curr += 1
    return result


cdef object parse_plist_dict_content(ParseInfo *pi):
    cdef object dict_type = <object>pi.dict_type
    result = dict_type()
    cdef object value
    cdef bint found_char
    cdef object key = parse_plist_string(pi, required=False)

    while key is not None:
        found_char = advance_to_non_space(pi)
        if not found_char:
            raise ParseError(
                "Missing ';' on line %d" % line_number_strings(pi)
            )

        if pi.curr[0] == c';':
            # This is a 'strings resource' file using the shortcut format,
            # although this check here really applies to all plists
            value = key
        elif pi.curr[0] == c'=':
            pi.curr += 1
            value = parse_plist_object(pi, required=True)
        else:
            raise ParseError(
                "Unexpected character after key at line %d: %r"
                % (line_number_strings(pi), pi.curr[0])
            )
        result[key] = value
        key = None
        value = None
        found_char = advance_to_non_space(pi)
        if found_char and pi.curr[0] == c';':
            pi.curr += 1
            key = parse_plist_string(pi, required=False)
        else:
            raise ParseError("Missing ';' on line %d" % line_number_strings(pi))

    return result


cdef object parse_plist_dict(ParseInfo *pi):
    result = parse_plist_dict_content(pi)
    if not advance_to_non_space(pi) or pi.curr[0] != c'}':
        raise ParseError(
            "Expected terminating '}' for dictionary at line %d"
            % line_number_strings(pi)
        )
    pi.curr += 1
    return result


cdef inline unsigned char from_hex_digit(unsigned char ch):
    if isdigit(ch):
        return ch - c'0'
    if ch >= c'a' and ch <= c'f':
        return ch - c'a' + 10
    elif ch >= c'A' and ch <= c'F':
        return ch - c'A' + 10
    return 0xff  # Just choose a large number for the error code


cdef int get_data_bytes(ParseInfo *pi, vector[unsigned char]& result) except -1:
    cdef unsigned char first, second
    cdef int num_bytes_read = 0
    cdef Py_UNICODE ch1, ch2
    while pi.curr < pi.end:
        ch1 = pi.curr[0]
        if ch1 == c'>':
            return 0
        first = from_hex_digit(<unsigned char>ch1)
        if first != 0xff:
            # if the first char is a hex, then try to read a second hex
            pi.curr += 1
            if pi.curr >= pi.end:
                raise ParseError(
                    "Malformed data byte group at line %d: uneven length"
                    % line_number_strings(pi)
                )
            ch2 = pi.curr[0]
            if ch2 == c'>':
                raise ParseError(
                    "Malformed data byte group at line %d: uneven length"
                    % line_number_strings(pi)
                )
            second = from_hex_digit(<unsigned char>ch2)
            if second == 0xff:
                raise ParseError(
                    "Malformed data byte group at line %d: invalid hex digit: %r"
                    % (line_number_strings(pi), ch2)
            )
            result.push_back((first << 4) + second)
            pi.curr += 1
        elif (
            ch1 == c' ' or
            ch1 == c'\n' or
            ch1 == c'\t' or
            ch1 == c'\r' or
            ch1 == 0x2028 or
            ch1 == 0x2029
        ):
            pi.curr += 1
        else:
            raise ParseError(
                "Malformed data byte group at line %d: invalid hex digit: %r"
                % (line_number_strings(pi), ch1)
            )


cdef bytes parse_plist_data(ParseInfo *pi):
    cdef vector[unsigned char] data
    get_data_bytes(pi, data)
    if pi.curr[0] == c">":
        pi.curr += 1  # move past '>'
        return PyBytes_FromStringAndSize(<const char*>data.const_data(), data.size())
    else:
        raise ParseError(
            "Expected terminating '>' for data at line %d"
            % line_number_strings(pi)
        )


cdef object parse_plist_object(ParseInfo *pi, bint required=True):
    cdef Py_UNICODE ch
    if not advance_to_non_space(pi):
        if required:
            raise ParseError("Unexpected EOF while parsing plist")
    ch = pi.curr[0]
    pi.curr += 1
    if ch == c'{':
        return parse_plist_dict(pi)
    elif ch == c'(':
        return parse_plist_array(pi)
    elif ch == c'<':
        return parse_plist_data(pi)
    elif ch == c'\'' or ch == c'"':
        return parse_quoted_plist_string(pi, ch)
    elif is_valid_unquoted_string_char(ch):
        pi.curr -= 1
        return parse_unquoted_plist_string(pi)
    else:
        pi.curr -= 1  # must back off the character we just read
        if required:
            raise ParseError(
                "Unexpected character at line %d: %r"
                % (line_number_strings(pi), ch)
            )


def loads(string, dict_type=dict, bint use_numbers=False):
    cdef unicode s = tounicode(string)
    cdef Py_ssize_t length = PyUnicode_GET_SIZE(s)
    cdef Py_UNICODE* buf = PyUnicode_AS_UNICODE(s)

    cdef ParseInfo pi = ParseInfo(
        begin=buf,
        curr=buf,
        end=buf + length,
        dict_type=<void *>dict_type,
        use_numbers=use_numbers,
    )

    cdef const Py_UNICODE *begin = pi.curr
    cdef object result = None
    if not advance_to_non_space(&pi):
        # a file consisting of only whitespace or empty is defined as an
        # empty dictionary
        result = {}
    else:
        result = parse_plist_object(&pi, required=True)
        if result:
            if advance_to_non_space(&pi):
                if not isinstance(result, unicode):
                    raise ParseError(
                        "Junk after plist at line %d" % line_number_strings(&pi)
                    )
                else:
                    # keep parsing for a 'strings resource' file: it looks like
                    # a dictionary without the opening/closing curly braces
                    pi.curr = begin
                    result = parse_plist_dict_content(&pi)

    return result


def load(fp, dict_type=dict, use_numbers=False):
    return loads(fp.read(), dict_type=dict_type, use_numbers=use_numbers)
