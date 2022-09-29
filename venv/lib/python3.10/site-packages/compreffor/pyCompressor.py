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
Tool to subroutinize a CFF OpenType font.

Usage (command line):
>> ./pyCompressor.py /path/to/font.otf
# font written to /path/to/font.compressed.otf

Usage (in Python):
>> font = TTFont(path_to_font)
>> compreffor = Compreffor(font)
>> compreffor.compress()
>> font.save(path_to_output)
"""

import itertools
import functools
import sys
import multiprocessing
import math
from collections import deque
import logging
from fontTools import cffLib
from fontTools.ttLib import TTFont
from fontTools.misc import psCharStrings
from compreffor import timer


log = logging.getLogger(__name__)


SINGLE_BYTE_OPS = set(['hstem',
                       'vstem',
                       'vmoveto',
                       'rlineto',
                       'hlineto',
                       'vlineto',
                       'rrcurveto',
                       'callsubr',
                       'return',
                       'endchar',
                       'blend',
                       'hstemhm',
                       'hintmask',
                       'cntrmask',
                       'rmoveto',
                       'hmoveto',
                       'vstemhm',
                       'rcurveline',
                       'rlinecurve',
                       'vvcurveto',
                       'hhcurveto',
                     # 'shortint',  # not really an operator
                       'callgsubr',
                       'vhcurveto',
                       'hvcurveto'])

__all__ = ["CandidateSubr", "SubstringFinder", "Compreffor", "compreff"]


def tokenCost(token):
        """Calculate the bytecode size of a T2 Charstring token"""

        tp = type(token)
        if issubclass(tp, str):
            if token[:8] in ("hintmask", "cntrmask"):
                return 1 + len(token[9:])
            elif token in SINGLE_BYTE_OPS:
                return 1
            else:
                return 2
        elif tp == tuple:
            assert token[0] in ("hintmask", "cntrmask")
            return 1 + len(token[1])
        elif tp == int:
            if -107 <= token <= 107:
                return 1
            elif 108 <= token <= 1131 or -1131 <= token <= -108:
                return 2
            else:
                return 3
        elif tp == float:
            return 5
        assert 0


class CandidateSubr(object):
    """
    Records a substring of a charstring that is generally
    repeated throughout many glyphs.

    Instance variables:
    length -- length of substring
    location -- tuple of form (glyph_idx, start_pos) where a ref string starts
    freq -- number of times it appears
    chstrings -- chstrings from whence this substring came
    cost_map -- array from simple alphabet -> actual token
    """

    __slots__ = ["length", "location", "freq", "chstrings", "cost_map", "_CandidateSubr__cost",
                 "_adjusted_cost", "_price", "_usages", "_list_idx", "_position", "_encoding",
                 "_program", "_flatten", "_max_call_depth", "_fdidx", "_global"]

    def __init__(self, length, ref_loc, freq=0, chstrings=None, cost_map=None):
        self.length = length
        self.location = ref_loc
        self.freq = freq
        self.chstrings = chstrings
        self.cost_map = cost_map

        self._global = False
        self._flatten = False
        self._fdidx = [] # indicates unreached subr

    def __len__(self):
        """Return the number of tokens in this substring"""

        return self.length

    def value(self):
        """Returns the actual substring value"""

        assert self.chstrings is not None

        return self.chstrings[self.location[0]][self.location[1]:(self.location[1] + self.length)]

    def subr_saving(self, use_usages=False, true_cost=False, call_cost=5, subr_overhead=3):
        """
        Return the savings that will be realized by subroutinizing
        this substring.

        Arguments:
        use_usages -- indicate to use the value in `_usages` rather than `freq`
        true_cost -- take account of subroutine calls
        call_cost -- the cost to call a subroutine
        subr_overhead -- the cost to define a subroutine
        """

        # NOTE: call_cost=5 gives better results for some reason
        #       but that is really not correct

        if use_usages:
            amt = self.usages()
        else:
            amt = self.frequency()

        if not true_cost:
            cost = self.cost()
        else:
            cost = self.real_cost(call_cost=call_cost)

        # TODO:
        # - If substring ends in "endchar", we need no "return"
        #   added and as such subr_overhead will be one byte
        #   smaller.
        # - The call_cost should be 3 or 4 if the position of the subr
        #   is greater
        return (  cost * amt # avoided copies
                - cost # cost of subroutine body
                - call_cost * amt # cost of calling
                - subr_overhead) # cost of subr definition

    def real_cost(self, call_cost=5):
        """Account for subroutine calls in cost computation. Not cached because
        the subroutines used will change over time."""

        cost = self.cost()
        cost += sum(-it[1].cost() + call_cost if not it[1]._flatten else it[1].real_cost(call_cost=call_cost)
                    for it in self.encoding())
        return cost

    def cost(self):
        """Return the size (in bytes) that the bytecode for this takes up"""

        assert self.cost_map is not None

        try:
            try:
                return self.__cost
            except AttributeError:
                self.__cost = sum([self.cost_map[t] for t in self.value()])
                return self.__cost
        except:
            raise Exception('Translated token not recognized')

    def encoding(self):
        return self._encoding

    def usages(self):
        return self._usages

    def frequency(self):
        return self.freq

    def __eq__(self, other):
        if not isinstance(other, CandidateSubr):
            return NotImplemented
        return self.length == other.length and self.location == other.location

    def __ne__(self, other):
        if not isinstance(other, CandidateSubr):
            return NotImplemented
        return not(self == other)

    def __hash__(self):
        return hash((self.length, self.location))

    def __repr__(self):
        return "<CandidateSubr: %d x %dreps>" % (self.length, self.freq)


class SubstringFinder(object):
    """
    This class facilitates the finding of repeated substrings
    within a glyph_set. Typical usage involves creation of an instance
    and then calling `get_substrings`, which returns a sorted list
    of `CandidateSubr`s.

    Instance variables:
    suffixes -- sorted array of suffixes
    data --
      A 2-level array of charstrings:
        - The first level separates by glyph
        - The second level separates by token
            in a glyph's charstring
    alphabet_size -- size of alphabet
    length -- sum of the lengths of the individual glyphstrings
    rev_keymap -- map from simple alphabet -> original tokens
    cost_map -- map from simple alphabet -> bytecost of token
    glyph_set_keys -- glyph_set_keys[i] gives the glyph id for data[i]
    _completed_suffixes -- boolean whether the suffix array is ready and sorted
    """

    __slots__ = ["suffixes", "data", "alphabet_size", "length", "substrings",
                 "rev_keymap", "glyph_set_keys", "_completed_suffixes",
                 "cost_map"]

    def __init__(self, glyph_set):
        self.rev_keymap = []
        self.cost_map = []
        self.data = []
        self.suffixes = []
        self.length = 0

        self.process_chstrings(glyph_set)

        self._completed_suffixes = False

    def process_chstrings(self, glyph_set):
        """Remap the charstring alphabet and put into self.data"""

        self.glyph_set_keys = sorted(glyph_set.keys())

        keymap = {} # maps charstring tokens -> simple integer alphabet

        next_key = 0

        for k in self.glyph_set_keys:
            char_string = glyph_set[k]._glyph
            char_string.decompile()
            program = []
            piter = iter(enumerate(char_string.program))
            for i, tok in piter:
                assert tok not in ("callsubr", "callgsubr", "return")
                assert tok != "endchar" or i == len(char_string.program) - 1
                if tok in ("hintmask", "cntrmask"):
                    # Attach next token to this, as a subroutine
                    # call cannot be placed between this token and
                    # the following.
                    _, tokennext = next(piter)
                    tok = (tok, tokennext)
                if not tok in keymap:
                    keymap[tok] = next_key
                    self.rev_keymap.append(tok)
                    self.cost_map.append(tokenCost(tok))
                    next_key += 1
                program.append(keymap[tok])

            program = tuple(program)
            chstr_len = len(program)
            self.length += chstr_len
            glyph_idx = len(self.data)
            self.suffixes.extend(
                    map(lambda x: (glyph_idx, x), range(chstr_len))
                )
            self.data.append(tuple(program))

        self.alphabet_size = next_key

    def get_suffixes(self):
        """Return the sorted suffix array"""

        if self._completed_suffixes:
            return self.suffixes

        with timer("get suffixes via Python sort"):
            self.suffixes.sort(key=lambda idx: self.data[idx[0]][idx[1]:])
            self._completed_suffixes = True

        return self.suffixes

    @timer("get LCP array")
    def get_lcp(self):
        """Returns the LCP array"""

        if not self._completed_suffixes:
            self.get_suffixes()

        assert self._completed_suffixes

        rank = [[0 for _ in range(len(d_list))] for d_list in self.data]
        lcp = [0 for _ in range(self.length)]

        # compute rank array
        for i in range(self.length):
            glyph_idx, tok_idx = self.suffixes[i]
            rank[glyph_idx][tok_idx] = i

        for glyph_idx in range(len(self.data)):
            cur_h = 0
            chstring = self.data[glyph_idx]
            for tok_idx in range(len(chstring)):
                cur_rank = rank[glyph_idx][tok_idx]
                if cur_rank > 0:
                    last_glidx, last_tidx = self.suffixes[cur_rank - 1]
                    last_chstring = self.data[last_glidx]
                    while last_tidx + cur_h < len(last_chstring) and \
                          tok_idx + cur_h < len(chstring) and \
                          last_chstring[last_tidx + cur_h] == self.data[glyph_idx][tok_idx + cur_h]:
                        cur_h += 1
                    lcp[cur_rank] = cur_h

                    if cur_h > 0:
                        cur_h -= 1

        return lcp

    def get_substrings(self, min_freq=2, check_positive=True, sort_by_length=False):
        """
        Return repeated substrings (type CandidateSubr) from the charstrings
        sorted by subroutine savings with freq >= min_freq using the LCP array.

        Arguments:
        min_freq -- the minimum frequency required to include a substring
        check_positive -- if True, only allow substrings with positive subr_saving
        sort_by_length -- if True, return substrings sorted by length, else by saving
        """

        self.get_suffixes()

        lcp = self.get_lcp()

        with timer("extract substrings"):
            start_indices = deque()
            self.substrings = []

            for i, min_l in enumerate(lcp):
                # First min_l items are still the same.

                # Pop the rest from previous and account for.
                # Note: non-branching substrings aren't included
                # TODO: don't allow overlapping substrings into the same set

                while start_indices and start_indices[-1][0] > min_l:
                    l, start_idx = start_indices.pop()
                    freq = i - start_idx
                    if freq < min_freq:
                        continue

                    substr = CandidateSubr(
                                           l,
                                           self.suffixes[start_idx],
                                           freq,
                                           self.data,
                                           self.cost_map)
                    if substr.subr_saving() > 0 or not check_positive:
                        self.substrings.append(substr)

                if not start_indices or min_l > start_indices[-1][0]:
                    start_indices.append((min_l, i - 1))

        log.debug("%d substrings found", len(self.substrings))
        with timer("sort substrings"):
            if sort_by_length:
                self.substrings.sort(key=lambda s: len(s))
            else:
                self.substrings.sort(key=lambda s: s.subr_saving(), reverse=True)
        return self.substrings


class Compreffor(object):
    """
    Manager class for the compreffor.

    Usage:
    >> font = TTFont(path_to_font)
    >> compreffor = Compreffor(font)
    >> compreffor.compress()
    >> font.save("/path/to/output.otf")
    """

    SINGLE_PROCESS = False
    ALPHA = 0.1
    K = 0.1
    PROCESSES = 12
    NROUNDS = 4
    LATIN_POOL_CHUNKRATIO = 0.05
    POOL_CHUNKRATIO = 0.1
    CHUNK_CHARSET_CUTOFF = 1500
    NSUBRS_LIMIT = 65533  # 64K - 3
    SUBR_NEST_LIMIT = 10

    def __init__(self, font, nrounds=None, max_subrs=None,
                 chunk_ratio=None, processes=None, test_mode=False):
        """
        Initialize the compressor.

        Arguments:
        font -- the TTFont to compress, must be a CFF font
        nrounds -- specifies the number of rounds to run
        max_subrs -- specify the limit on the number of subrs in an INDEX
        chunk_ratio -- sets the POOL_CHUNKRATIO parameter
        processes -- specify the number of parallel processes (1 to not
            parallelize)
        test_mode -- disables some checks (such as positive subr_saving)
        """

        if isinstance(font, TTFont):
            assert "CFF " in font
            assert len(font["CFF "].cff.topDictIndex) == 1
            self.font = font
        else:
            log.warning("non-TTFont given to Compreffor")
        self.test_mode = test_mode

        if chunk_ratio is not None:
            self.POOL_CHUNKRATIO = chunk_ratio
        elif font and (len(font["CFF "].cff.topDictIndex[0].charset) <
                       self.CHUNK_CHARSET_CUTOFF):
            self.POOL_CHUNKRATIO = self.LATIN_POOL_CHUNKRATIO
        if nrounds is not None:
            self.NROUNDS = nrounds
        if processes is not None:
            if processes < 1:
                raise ValueError('processes value must be > 0')
            elif processes == 1:
                self.SINGLE_PROCESS = True
            else:
                self.PROCESSES = processes
        if max_subrs is not None:
            self.NSUBRS_LIMIT = max_subrs
        # only print the progress in `iterative_encode` if the logger is
        # enabled for DEBUG, and if it outputs to the console's stderr
        self._progress = (not log.disabled and log.isEnabledFor(logging.DEBUG)
                          and _has_stderr_handler(log))

    def compress(self):
        """Compress the provided font using the iterative method"""

        top_dict = self.font["CFF "].cff.topDictIndex[0]

        multi_font = hasattr(top_dict, "FDArray")

        if not multi_font:
            n_locals = 1
            fdsel = None
        else:
            n_locals = len(top_dict.FDArray)
            fdsel = lambda g: top_dict.CharStrings.getItemAndSelector(g)[1]

        ans = self.iterative_encode(self.font.getGlyphSet(),
                                    fdsel,
                                    n_locals)

        encoding = ans["glyph_encodings"]
        gsubrs = ans["gsubrs"]
        lsubrs = ans["lsubrs"]

        Compreffor.apply_subrs(top_dict, encoding, gsubrs, lsubrs)

    @staticmethod
    @timer("apply subroutines")
    def apply_subrs(top_dict, encoding, gsubrs, lsubrs):
        multi_font = hasattr(top_dict, "FDArray")
        gbias = psCharStrings.calcSubrBias(gsubrs)
        lbias = [psCharStrings.calcSubrBias(subrs) for subrs in lsubrs]

        if multi_font:
            for g in top_dict.charset:
                charstring, sel = top_dict.CharStrings.getItemAndSelector(g)
                enc = encoding[g]
                Compreffor.collapse_hintmask(charstring.program)
                Compreffor.update_program(charstring.program, enc, gbias, lbias, sel)
                Compreffor.expand_hintmask(charstring.program)

            for fd in top_dict.FDArray:
                if not hasattr(fd.Private, "Subrs"):
                    fd.Private.Subrs = cffLib.SubrsIndex()

            for subrs, subrs_index in zip(itertools.chain([gsubrs], lsubrs),
                                          itertools.chain([top_dict.GlobalSubrs],
                                          [fd.Private.Subrs for fd in top_dict.FDArray])):
                for subr in subrs:
                    item = psCharStrings.T2CharString(program=subr._program)
                    subrs_index.append(item)

            for fd in top_dict.FDArray:
                if not fd.Private.Subrs:
                    del fd.Private.Subrs
        else:
            for glyph, enc in encoding.items():
                charstring = top_dict.CharStrings[glyph]
                Compreffor.collapse_hintmask(charstring.program)
                Compreffor.update_program(charstring.program, enc, gbias, lbias, 0)
                Compreffor.expand_hintmask(charstring.program)

            assert len(lsubrs) == 1

            if not hasattr(top_dict.Private, "Subrs"):
                top_dict.Private.Subrs = cffLib.SubrsIndex()

            for subr in lsubrs[0]:
                item = psCharStrings.T2CharString(program=subr._program)
                top_dict.Private.Subrs.append(item)

            if not top_dict.Private.Subrs:
                del top_dict.Private.Subrs

            for subr in gsubrs:
                item = psCharStrings.T2CharString(program=subr._program)
                top_dict.GlobalSubrs.append(item)

    @staticmethod
    def test_call_cost(subr, subrs):
        """See how much it would cost to call subr if it were inserted into subrs"""

        if len(subrs) >= 2263:
            if subrs[2262].usages() >= subr.usages():
                return 3
        if len(subrs) >= 215:
            if subrs[214].usages() >= subr.usages():
                return 2
        return 1

    @staticmethod
    def insert_by_usage(subr, subrs):
        """Insert subr into subrs mainting a sort by usage"""

        subrs.append(subr)
        subrs.sort(key=lambda s: s.usages(), reverse=True)

    def iterative_encode(self, glyph_set, fdselect=None, fdlen=1):
        """
        Choose a subroutinization encoding for all charstrings in
        `glyph_set` using an iterative Dynamic Programming algorithm.
        Initially uses the results from SubstringFinder and then
        iteratively optimizes.

        Arguments:
        glyph_set -- the set of charstrings to encode (required)
        fdselect -- the FDSelect array of the source font, or None
        fdlen -- the number of FD's in the source font, or 1 if there are none

        Returns:
        A three-part dictionary with keys 'gsubrs', 'lsubrs', and
        'glyph_encodings'. The 'glyph_encodings' encoding dictionary
        specifies how to break up each charstring. Encoding[i]
        describes how to encode glyph i. Each entry is something
        like [(x_1, c_1), (x_2, c_2), ..., (x_k, c_k)], where x_* is an index
        into the charstring that indicates where a subr starts and c_*
        is a CandidateSubr. The 'gsubrs' entry contains an array of global
        subroutines (CandidateSubr objects) and 'lsubrs' is an array indexed
        by FDidx, where each entry is a list of local subroutines.
        """

        # generate substrings for marketplace
        sf = SubstringFinder(glyph_set)

        if self.test_mode:
            substrings = sf.get_substrings(min_freq=0, check_positive=False, sort_by_length=False)
        else:
            substrings = sf.get_substrings(min_freq=2, check_positive=True, sort_by_length=False)

        # TODO remove unnecessary substrings?

        data = sf.data
        rev_keymap = sf.rev_keymap
        cost_map = sf.cost_map
        glyph_set_keys = sf.glyph_set_keys
        del sf

        if not self.SINGLE_PROCESS:
            pool = multiprocessing.Pool(processes=self.PROCESSES)
        else:
            class DummyPool:
                pass
            pool = DummyPool()
            pool.map = lambda f, *l, **kwargs: map(f, *l)

        substr_dict = {}

        timer.split()

        log.debug("glyphstrings+substrings=%d", len(data) + len(substrings))

        # set up dictionary with initial values
        for idx, substr in enumerate(substrings):
            substr._adjusted_cost = substr.cost()
            substr._price = substr._adjusted_cost
            substr._usages = substr.freq # this is the frequency that the substring appears,
                                        # not necessarily used
            substr._list_idx = idx
            substr_dict[substr.value()] = (idx, substr._price) # NOTE: avoid excess data copying on fork
                                                               # probably can just pass substr
                                                               # if threading instead

        for run_count in range(self.NROUNDS):
            # calibrate prices
            for idx, substr in enumerate(substrings):
                marg_cost = float(substr._adjusted_cost) / (substr._usages + self.K)
                substr._price = marg_cost * self.ALPHA + substr._price * (1 - self.ALPHA)
                substr_dict[substr.value()] = (idx, substr._price)

            # minimize substring costs
            csize = int(math.ceil(self.POOL_CHUNKRATIO*len(substrings)))
            substr_encodings = pool.map(functools.partial(optimize_charstring,
                                                          cost_map=cost_map,
                                                          substr_dict=substr_dict,
                                                          progress=self._progress),
                                        enumerate([s.value() for s in substrings]),
                                        chunksize=csize)

            for substr, result in zip(substrings, substr_encodings):
                substr._encoding = [(enc_item[0], substrings[enc_item[1]]) for enc_item in result["encoding"]]
                substr._adjusted_cost = result["market_cost"]
            del substr_encodings

            # minimize charstring costs in current market through DP
            csize = int(math.ceil(self.POOL_CHUNKRATIO*len(data)))
            encodings = pool.map(functools.partial(optimize_charstring,
                                                   cost_map=cost_map,
                                                   substr_dict=substr_dict,
                                                   progress=self._progress),
                                 data,
                                 chunksize=csize)
            encodings = [[(enc_item[0], substrings[enc_item[1]]) for enc_item in i["encoding"]] for i in encodings]

            # update substring frequencies based on cost minimization
            for substr in substrings:
                substr._usages = 0

            for calling_substr in substrings:
                for start, substr in calling_substr._encoding:
                    if substr:
                        substr._usages += 1
            for glyph_idx, enc in enumerate(encodings):
                for start, substr in enc:
                    if substr:
                        substr._usages += 1

            if log.isEnabledFor(logging.INFO):
                log.info("Round %d Done!", (run_count + 1))
                log.info("avg: %f", (float(sum(substr._usages for substr in substrings)) / len(substrings)))
                log.info("max: %d", max(substr._usages for substr in substrings))
                log.info("used: %d", sum(substr._usages > 0 for substr in substrings))

            if run_count <= self.NROUNDS - 2 and not self.test_mode:
                with timer("cutdown"):
                    if run_count < self.NROUNDS - 2:
                        bad_substrings = [s for s in substrings if s.subr_saving(use_usages=True) <= 0]
                        substrings = [s for s in substrings if s.subr_saving(use_usages=True) > 0]
                    else:
                        bad_substrings = [s for s in substrings if s.subr_saving(use_usages=True, true_cost=False) <= 0]
                        substrings = [s for s in substrings if s.subr_saving(use_usages=True, true_cost=False) > 0]

                    for substr in bad_substrings:
                        # heuristic to encourage use of called substrings:
                        for idx, called_substr in substr._encoding:
                            called_substr._usages += substr._usages - 1
                        del substr_dict[substr.value()]
                    for idx, s in enumerate(substrings):
                        s._list_idx = idx
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("%d substrings with non-positive savings removed", len(bad_substrings))
                        log.debug("(%d had positive usage)", len([s for s in bad_substrings if s._usages > 0]))

        log.info("Finished iterative market (%gs)", timer.split())
        log.info("%d candidate subrs found", len(substrings))

        gsubrs, lsubrs = Compreffor.process_subrs(
                                            glyph_set_keys,
                                            encodings,
                                            fdlen,
                                            fdselect,
                                            substrings,
                                            rev_keymap,
                                            self.NSUBRS_LIMIT,
                                            self.SUBR_NEST_LIMIT)

        return {"glyph_encodings": dict(zip(glyph_set_keys, encodings)),
                "lsubrs": lsubrs,
                "gsubrs": gsubrs}

    @staticmethod
    @timer("post-process subroutines")
    def process_subrs(glyph_set_keys, encodings, fdlen, fdselect, substrings, rev_keymap, subr_limit, nest_limit):

        def mark_reachable(cand_subr, fdidx):
            try:
                if fdidx not in cand_subr._fdidx:
                    cand_subr._fdidx.append(fdidx)
            except AttributeError:
                cand_subr._fdidx = [fdidx]

            for it in cand_subr._encoding:
                mark_reachable(it[1], fdidx)
        if fdselect is not None:
            for g, enc in zip(glyph_set_keys, encodings):
                sel = fdselect(g)
                for it in enc:
                    mark_reachable(it[1], sel)
        else:
            for encoding in encodings:
                for it in encoding:
                    mark_reachable(it[1], 0)

        subrs = [s for s in substrings if s.usages() > 0 and hasattr(s, '_fdidx') and  bool(s._fdidx) and s.subr_saving(use_usages=True, true_cost=True) > 0]

        bad_substrings = [s for s in substrings if s.usages() == 0 or not hasattr(s, '_fdidx') or not bool(s._fdidx) or s.subr_saving(use_usages=True, true_cost=True) <= 0]
        log.debug("%d substrings unused or negative saving subrs", len(bad_substrings))

        for s in bad_substrings:
            s._flatten = True

        gsubrs = []
        lsubrs = [[] for _ in range(fdlen)]

        subrs.sort(key=lambda s: s.subr_saving(use_usages=True, true_cost=True))

        while subrs and (any(len(s) < subr_limit for s in lsubrs) or
                         len(gsubrs) < subr_limit):
            subr = subrs[-1]
            del subrs[-1]
            if len(subr._fdidx) == 1:
                lsub_index = lsubrs[subr._fdidx[0]]
                if len(gsubrs) < subr_limit:
                    if len(lsub_index) < subr_limit:
                        # both have space
                        gcost = Compreffor.test_call_cost(subr, gsubrs)
                        lcost = Compreffor.test_call_cost(subr, lsub_index)

                        if gcost < lcost:
                            Compreffor.insert_by_usage(subr, gsubrs)
                            subr._global = True
                        else:
                            Compreffor.insert_by_usage(subr, lsub_index)
                    else:
                        # just gsubrs has space
                        Compreffor.insert_by_usage(subr, gsubrs)
                        subr._global = True
                elif len(lsub_index) < subr_limit:
                    # just lsubrs has space
                    Compreffor.insert_by_usage(subr, lsub_index)
                else:
                    # we must skip :(
                    bad_substrings.append(subr)
            else:
                if len(gsubrs) < subr_limit:
                    # we can put it in globals
                    Compreffor.insert_by_usage(subr, gsubrs)
                    subr._global = True
                else:
                    # no room for this one
                    bad_substrings.append(subr)

        bad_substrings.extend([s[1] for s in subrs])  # add any leftover subrs to bad_substrings

        if fdselect is not None:
            # CID-keyed: Avoid `callsubr` usage in global subroutines
            bad_lsubrs = Compreffor.collect_lsubrs_called_from(gsubrs)
            bad_substrings.extend(bad_lsubrs)
            lsubrs = [[s for s in lsubrarr if s not in bad_lsubrs] for lsubrarr in lsubrs]

        for s in bad_substrings:
            s._flatten = True

        # fix any nesting issues
        Compreffor.calc_nesting(gsubrs)
        for subrs in lsubrs:
            Compreffor.calc_nesting(subrs)

        too_nested = [s for s in itertools.chain(*lsubrs) if s._max_call_depth > nest_limit]
        too_nested.extend([s for s in gsubrs if s._max_call_depth > nest_limit])
        for s in too_nested:
            s._flatten = True
        bad_substrings.extend(too_nested)
        lsubrs = [[s for s in lsubrarr if s._max_call_depth <= nest_limit] for lsubrarr in lsubrs]
        gsubrs = [s for s in gsubrs if s._max_call_depth <= nest_limit]
        too_nested = len(too_nested)

        log.debug("%d substrings nested too deep", too_nested)
        log.debug("%d substrings being flattened", len(bad_substrings))

        # reorganize to minimize call cost of most frequent subrs
        gbias = psCharStrings.calcSubrBias(gsubrs)
        lbias = [psCharStrings.calcSubrBias(s) for s in lsubrs]

        for subr_arr, bias in zip(itertools.chain([gsubrs], lsubrs),
                                  itertools.chain([gbias], lbias)):
            subr_arr.sort(key=lambda s: s.usages(), reverse=True)

            if bias == 1131:
                subr_arr[:] = subr_arr[216:1240] + subr_arr[0:216] + subr_arr[1240:]
            elif bias == 32768:
                subr_arr[:] = (subr_arr[2264:33901] + subr_arr[216:1240] +
                            subr_arr[0:216] + subr_arr[1240:2264] + subr_arr[33901:])
            for idx, subr in enumerate(subr_arr):
                subr._position = idx

        for subr in sorted(bad_substrings, key=lambda s: len(s)):
            # NOTE: it is important this is run in order so shorter
            # substrings are run before longer ones
            if hasattr(subr, '_fdidx') and len(subr._fdidx) > 0:
                program = [rev_keymap[tok] for tok in subr.value()]
                Compreffor.update_program(program, subr.encoding(), gbias, lbias, None)
                Compreffor.expand_hintmask(program)
                subr._program = program

        for subr_arr, sel in zip(itertools.chain([gsubrs], lsubrs),
                                  itertools.chain([None], range(fdlen))):
            for subr in subr_arr:
                program = [rev_keymap[tok] for tok in subr.value()]
                if program[-1] not in ("endchar", "return"):
                    program.append("return")
                Compreffor.update_program(program, subr.encoding(), gbias, lbias, sel)
                Compreffor.expand_hintmask(program)
                subr._program = program

        return (gsubrs, lsubrs)

    @staticmethod
    def collect_lsubrs_called_from(gsubrs):
        """
        Collect local subroutines called from any entries in `gsubrs`.
        This method returns them as a set for after flattening
        in order to avoid `callsubr` usage in global subroutines.
        """

        lsubrs = set()

        def collect(subr):
            for _, s in subr._encoding:
                if not s._global:
                    lsubrs.add(s)
                    collect(s)

        for subr in gsubrs:
            collect(subr)
        return lsubrs

    @staticmethod
    def calc_nesting(subrs):
        """Update each entry of subrs with their call depth. This
        is stored in the '_max_call_depth' attribute of the subr"""

        def increment_subr_depth(subr, depth):
            if not hasattr(subr, "_max_call_depth") or subr._max_call_depth < depth:
                subr._max_call_depth = depth

            callees = deque([it[1] for it in subr._encoding])

            while len(callees):
                next_subr = callees.pop()
                if next_subr._flatten:
                    callees.extend([it[1] for it in next_subr._encoding])
                elif (not hasattr(next_subr, "_max_call_depth") or
                            next_subr._max_call_depth < depth + 1):
                        increment_subr_depth(next_subr, depth + 1)

        for subr in subrs:
            if not hasattr(subr, "_max_call_depth"):
                increment_subr_depth(subr, 1)

    @staticmethod
    def update_program(program, encoding, gbias, lbias_arr, fdidx):
        """
        Applies the provided `encoding` to the provided `program`. I.e., all
        specified subroutines are actually called in the program. This mutates
        the input program and also returns it.

        Arguments:
        program -- the program to update
        encoding -- the encoding to use. a list of (idx, cand_subr) tuples
        gbias -- bias into the global subrs INDEX
        lbias_arr -- bias into each of the lsubrs INDEXes
        fdidx -- the FD that this `program` belongs to, or None if global
        """

        offset = 0
        for item in encoding:
            subr = item[1]
            s = slice(item[0] - offset, item[0] + subr.length - offset)
            if subr._flatten:
                program[s] = subr._program
                offset += subr.length - len(subr._program)
            else:
                assert hasattr(subr, "_position"), \
                        "CandidateSubr without position in Subrs encountered"

                if subr._global:
                    operator = "callgsubr"
                    bias = gbias
                else:
                    # assert this is a local or global only used by one FD
                    assert len(subr._fdidx) == 1
                    assert fdidx == None or subr._fdidx[0] == fdidx
                    operator = "callsubr"
                    bias = lbias_arr[subr._fdidx[0]]

                program[s] = [subr._position - bias, operator]
                offset += subr.length - 2
        return program

    @staticmethod
    def collapse_hintmask(program):
        """Takes in a charstring and returns the same charstring
        with hintmasks combined into a single element"""

        piter = iter(enumerate(program))

        for i, tok in piter:
            if tok in ("hintmask", "cntrmask"):
                program[i:i+2] = [(program[i], program[i+1])]

    @staticmethod
    def expand_hintmask(program):
        """Expands collapsed hintmask tokens into two tokens"""

        piter = iter(enumerate(program))

        for i, tok in piter:
            if isinstance(tok, tuple):
                assert tok[0] in ("hintmask", "cntrmask")
                program[i:i+1] = tok


def _has_stderr_handler(logger):
    """ Return True if any of the logger's handlers outputs to sys.stderr. """
    c = logger
    while c:
        if c.handlers:
            for h in c.handlers:
                if hasattr(h, 'stream') and h.stream is sys.stderr:
                    return True
        if not c.propagate:
            break
        else:
            c = c.parent
    return False


def optimize_charstring(charstring, cost_map, substr_dict, progress=False):
    """Optimize a charstring (encoded using keymap) using
    the substrings in substr_dict. This is the Dynamic Programming portion
    of `iterative_encode`."""

    if len(charstring) > 1 and type(charstring[1]) == tuple:
        if type(charstring[0]) == int:
            skip_idx = charstring[0]
            charstring = charstring[1]
    else:
        skip_idx = None

    results = [0 for _ in range(len(charstring) + 1)]
    next_enc_idx = [None for _ in range(len(charstring))]
    next_enc_substr = [None for _ in range(len(charstring))]
    for i in reversed(range(len(charstring))):
        min_option = float("inf")
        min_enc_idx = len(charstring)
        min_enc_substr = None
        cur_cost = 0
        for j in range(i + 1, len(charstring) + 1):
            cur_cost += cost_map[charstring[j - 1]]

            if charstring[i:j] in substr_dict:
                substr = substr_dict[charstring[i:j]]
                if substr[0] != skip_idx:
                    option = substr[1] + results[j]
                    substr = substr[0]
                else:
                    assert i == 0 and j == len(charstring)
                    substr = None
                    option = cur_cost + results[j]
            else:
                # note: must not be branching, so just make _price actual cost
                substr = None
                option = cur_cost + results[j]

            if option < min_option:
                min_option = option
                min_enc_idx = j
                min_enc_substr = substr

        results[i] = min_option
        next_enc_idx[i] = min_enc_idx
        next_enc_substr[i] = min_enc_substr

    market_cost = results[0]
    encoding = []
    cur_enc_idx = 0
    last = len(next_enc_idx)
    while cur_enc_idx < last:
        last_idx = cur_enc_idx
        cur_enc_substr = next_enc_substr[cur_enc_idx]
        cur_enc_idx = next_enc_idx[cur_enc_idx]

        if cur_enc_substr is not None:
            encoding.append((last_idx, cur_enc_substr))

    if progress:
        sys.stderr.write(".")
        sys.stderr.flush()
    return {"encoding": encoding, "market_cost": market_cost}


# this is here for symmetry with cxxCompressor.compreff

def compreff(font, **options):
    """ Main function that compresses `font`, a TTFont object, in place. """
    Compreffor(font, **options).compress()


def human_size(num):
    """Return a number of bytes in human-readable units"""

    num = float(num)
    for s in ['bytes', 'KB', 'MB']:
        if num < 1024.0:
            return '%3.1f %s' % (num, s)
        else:
            num /= 1024.0
    return '%3.1f %s' % (num, 'GB')
