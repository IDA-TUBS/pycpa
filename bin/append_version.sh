#!/bin/sh
# This scripts appends the current mercurial tip version
# as a __version__ variable to the __init__.py of a module
# The module can be supplied as an argument. If missing, pycpa is used.

if [ -z "$1" ] 
then
    module="pycpa"
else
    module="$1"
fi

echo -e "__version__ = '`hg id -i`'\n" >> $module/__init__.py
