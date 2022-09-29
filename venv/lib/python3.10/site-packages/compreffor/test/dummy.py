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

import collections.abc


class DummyGlyphSet(collections.abc.MutableMapping):
    """Behaves like a glyphset for testing purposes"""

    def __init__(self, *args, **kwargs):
        self.storage = {}
        self.update(dict(*args, **kwargs)) # interpret initial args

    def __getitem__(self, key):
        return self.storage[key]

    def __setitem__(self, key, value):
        self.storage[key] = self.DummyCharString(value)

    def __delitem__(self, key):
        del self.storage[key]

    def __iter__(self):
        return iter(self.storage)

    def __len__(self):
        return len(self.storage)

    class DummyCharString(object):
        program = None

        def __init__(self, data):
            self.program = data
            self._glyph = self

        def decompile(self):
            pass

        def __iter__(self):
            return iter(self.program)

        def __repr__(self):
            return repr(self.program)

        def __str__(self):
            return str(self.program)

        def __len__(self):
            return len(self.program)
