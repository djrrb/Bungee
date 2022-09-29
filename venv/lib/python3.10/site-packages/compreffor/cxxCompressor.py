#!/usr/bin/env python
#
# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tool to subroutinize a CFF OpenType font. Backed by a C++ binary.

This file is a bootstrap for the C++ edition of the FontTools compreffor.
It prepares the input data for the extension and reads back in the results,
applying them to the input font.

Usage (command line):
>> ./cxxCompressor.py /path/to/font.otf
# font written to /path/to/font.compressed.otf

Usage (python):
>> font = TTFont("/path/to/font.otf")
>> cxxCompressor.compreff(font)
>> font.save("/path/to/output.otf")
"""

import array
from io import BytesIO
import struct
import logging
from compreffor.pyCompressor import (
    Compreffor, CandidateSubr, tokenCost)
from compreffor import _compreffor as lib, timer


log = logging.getLogger(__name__)

__all__ = ["compreff"]


class IdKeyMap(object):
    """A map that where every key's value is itself. Used
    as a map from simplified key space to actual key space
    in pyCompressor"""

    def __getitem__(self, tok):
        return tok


class SimpleCandidateSubr(CandidateSubr):
    """A reimplimentation of CandidateSubr to be more
    compatible with results from C++"""

    def __init__(self, length, ref_loc):
        self.length = length
        self.location = ref_loc
        self.freq = 0
        self._flatten = False
        self._global = False

    def usages(self):
        return self.freq

    frequency = usages

    def cost(self):
        try:
            return self.__cost
        except AttributeError:
            self.__cost = sum(map(tokenCost, self.value()))
            return self.__cost

    def encoding(self):
        return self._encoding


@timer("produce data for C++ library")
def write_data(td):
    """Writes CharStrings from the TopDict td into a string that is easily
    readable."""

    out = BytesIO()
    td.CharStrings.charStringsIndex.getCompiler(td.strings, None).toFile(out)
    return out.getvalue()


def get_encoding(data_buffer, subrs):
    """Read a charstring's encoding stream out of a string buffer response
    from cffCompressor.cc"""

    pos = 0
    num_calls = data_buffer[pos]
    pos += 1
    enc = []
    for j in range(num_calls):
        insertion_pos = struct.unpack_from('<I', data_buffer[pos:pos+4])[0]
        pos += 4
        subr_index = struct.unpack_from('<I', data_buffer[pos:pos+4])[0]
        pos += 4
        subrs[subr_index].freq += 1
        enc.append((insertion_pos, subrs[subr_index]))
    return enc, pos


def read_data(td, result_string):
    """Read the output of cffCompressor.cc into Python data
    structures."""

    results = array.array("B", result_string)
    num_subrs = struct.unpack_from('<I', results[:4])[0]

    # process subrs
    subrs = []
    pos = 4
    for i in range(num_subrs):
        glyph_idx = struct.unpack_from('<I', results[pos:pos+4])[0]
        pos += 4
        tok_idx = struct.unpack_from('<I', results[pos:pos+4])[0]
        pos += 4
        subr_len = struct.unpack_from('<I', results[pos:pos+4])[0]
        pos += 4
        subrs.append(SimpleCandidateSubr(subr_len, (glyph_idx, tok_idx)))
    for i in range(num_subrs):
        enc, num_read = get_encoding(results[pos:], subrs)
        pos += num_read
        subrs[i]._encoding = enc

    # process glyph encodings
    glyph_encodings = []
    for i in range(len(td.CharStrings)):
        enc, num_read = get_encoding(results[pos:], subrs)
        pos += num_read
        glyph_encodings.append(enc)

    assert pos == len(results)
    return (subrs, glyph_encodings)


@timer("extract results")
def interpret_data(td, results):
    """Interpret the result array from a lib.compreff call to
    produce Python data structures."""

    class MutableSpace: pass
    MutableSpace.pos = 0
    def pop_result():
        ans = results[MutableSpace.pos]
        MutableSpace.pos += 1
        return ans

    num_subrs = pop_result()

    # process subrs
    subrs = []
    for i in range(num_subrs):
        glyph_idx = pop_result()
        tok_idx = pop_result()
        subr_len = pop_result()
        subrs.append(SimpleCandidateSubr(subr_len, (glyph_idx, tok_idx)))

    def pop_encoding():
        num_calls = pop_result()
        enc = []
        for j in range(num_calls):
            insertion_pos = pop_result()
            subr_index = pop_result()
            subrs[subr_index].freq += 1
            enc.append((insertion_pos, subrs[subr_index]))
        return enc

    for i in range(num_subrs):
        enc = pop_encoding()
        subrs[i]._encoding = enc

    # process glyph encodings
    glyph_encodings = []
    for i in range(len(td.CharStrings)):
        enc = pop_encoding()
        glyph_encodings.append(enc)

    return (subrs, glyph_encodings)


@timer("compress the font")
def compreff(font, nrounds=None, max_subrs=None):
    """Main function that compresses `font`, a TTFont object,
    in place.
    """
    assert len(font['CFF '].cff.topDictIndex) == 1

    td = font['CFF '].cff.topDictIndex[0]

    if nrounds is None:
        nrounds = Compreffor.NROUNDS
    if max_subrs is None:
        max_subrs = Compreffor.NSUBRS_LIMIT

    input_data = write_data(td)
    with timer("run 'lib.compreff()'"):
        results = lib.compreff(input_data, nrounds)
    subrs, glyph_encodings = interpret_data(td, results)

    with timer("decompile charstrings"):
        for cs in td.CharStrings.values():
            cs.decompile()

    # in order of charset
    chstrings = [x.program for x in td.CharStrings.values()]
    for cs in chstrings:
        Compreffor.collapse_hintmask(cs)

    for s in subrs:
        s.chstrings = chstrings

    if hasattr(td, 'FDSelect'):
        fdselect = lambda g: td.CharStrings.getItemAndSelector(g)[1]
        fdlen = len(td.FDArray)
    else:
        fdselect = None
        fdlen = 1

    nest_limit = Compreffor.SUBR_NEST_LIMIT
    gsubrs, lsubrs = Compreffor.process_subrs(
                            td.charset,
                            glyph_encodings,
                            fdlen,
                            fdselect,
                            subrs,
                            IdKeyMap(),
                            max_subrs,
                            nest_limit)

    encoding = dict(zip(td.charset, glyph_encodings))

    Compreffor.apply_subrs(td, encoding, gsubrs, lsubrs)
