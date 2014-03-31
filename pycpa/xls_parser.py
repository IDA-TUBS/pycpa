"""
| Copyright (C) 2014 Daniel Thiele
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Daniel Thiele (thiele@ida.ing.tu-bs.de)

Description
-----------

Parser XLS(X) file to dictionary
"""


from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import re
import xlrd


def xls_letter_to_col(self, letters):
    """ Excel uses upper-case letters as column identifiers. This function
        converts them to integers, i.e. A -> 0, ..., AA -> 26, etc.
    """
    assert re.match(re.compile(r"^[A-Z]*$"), letters), \
    'Invalid column ID: %s' % str(letters)

    sum = 0
    i = 1
    for c in letters[::-1]:
        sum += i * (ord(c) + 1 - ord('A'))
        i *= 26
    assert sum > 0

    return sum - 1


class XLS_parser(object):
    """ Parse XLS workbook. Data is stored in a dict-list-dict hierarchy,
        i.e. self.sheets is a dict of worksheets, which contain a list of
        all data lines of that worksheet. Each of these lines is a dict
        using the entries of the header line as keys. The header is
        expected to be in the first line. All other entries are treated
        as data.
    """

    def __init__(self, filename):
        self.filename = filename
        self.workbook = None

        self.header = dict()    # dict of headers
        self.sheets = dict()    # dict of worksheets


    def get_line_of_sheet(self, sheet_name, line, use_xls_line_numbers=False):
        """ Get a certain line of a worksheet. Indexing, by default, starts
            at 0. Set use_xls_line_numbers to True to use indexing of XLS file.
        """
        if use_xls_line_numbers:
            assert line >= 2
            line -= 2

        return self.sheets[sheet_name][line]


    def get_line_entry_of_sheet(self, sheet_name, line, element_name, use_xls_line_numbers=False):
        """ Get a certain element of the given line in a sheet.
        """
        return self.get_line_of_sheet(sheet_name, line, \
            use_xls_line_numbers)[element_name]


    def parse(self):
        """ Parse XLS(X) file.
        """
        self.workbook = xlrd.open_workbook(self.filename)

        # Iterate over all sheets
        for sn in self.workbook.sheet_names():
            self.sheets[sn] = self._parse_worksheet(sn)

        return self.sheets


    def _parse_worksheet(self, worksheet_name):
        """ Parse a given worksheet.
        """
        sheet = self.workbook.sheet_by_name(worksheet_name)
        result = list()

        self.header[worksheet_name] = sheet.row_values(0)
        assert len(self.header[worksheet_name]) == len(set(self.header[worksheet_name])), \
            "Worksheet header of \"%s\" appears to have duplicate entries." % worksheet_name

        for l in range(1, sheet.nrows):
            line_dict = dict()

            row_values = sheet.row_values(l)
            for i in range(0, len(row_values)):
                line_dict[str(self.header[worksheet_name][i])] = row_values[i]

            result.append(line_dict)

        return result




# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
