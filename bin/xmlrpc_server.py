#!/usr/bin/env python
"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

XML-RPC server for pyCPA. It can be used to interface pycpa with
non-python (i.e. close-source) applications.
"""


from twisted.web import xmlrpc, server

from pycpa import options
from pycpa import cparpc

options.parser.add_argument('--port', '-p', type=int, default=7080,
        help='http port to listen on')


if __name__ == '__main__':
    from twisted.internet import reactor
    options.init_pycpa()
    rpc = cparpc.CPARPC()
    xmlrpc.addIntrospection(rpc)
    reactor.listenTCP(options.get_opt("port"), server.Site(rpc))
    reactor.run()
