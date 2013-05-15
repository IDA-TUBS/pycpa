"""
| Copyright (C) 2011 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer
"""


__author__ = "Jonas Diemer, Philip Axer"
__copyright__ = "Copyright (C) 2010-2013, TU Braunschweig, Germany. All rights reserved."

__license__ = "MIT"
__license_text__ = __copyright__ + """

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

# Try to determine the repository version from the file pycpa/VERSION
# This file is best created by an post-update hook, so add this to the
# .hg/hgrc:
# [hooks]
# post-update = hg id --id > pycpa/VERSION

import os
path = os.path.dirname(__file__)
try:
    f = open(path + '/VERSION')
    __version__ = "Version " + f.readline()
except IOError:
    __version__ = "Research Version\n"


__all__ = ["model", "analysis", "path_analysis", "options", "graph", "cparpc"]
