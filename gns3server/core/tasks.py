#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import asyncio

from typing import Callable
from fastapi import FastAPI

from gns3server.controller import Controller
from gns3server.compute import MODULES
from gns3server.compute.port_manager import PortManager
from gns3server.utils.http_client import HTTPClient
#from gns3server.db.tasks import connect_to_db, close_db_connection

import logging
log = logging.getLogger(__name__)


def create_startup_handler(app: FastAPI) -> Callable:

    async def start_app() -> None:
        loop = asyncio.get_event_loop()
        logger = logging.getLogger("asyncio")
        logger.setLevel(logging.ERROR)

        if sys.platform.startswith("win"):
            # Add a periodic callback to give a chance to process signals on Windows
            # because asyncio.add_signal_handler() is not supported yet on that platform
            # otherwise the loop runs outside of signal module's ability to trap signals.

            def wakeup():
                loop.call_later(0.5, wakeup)

            loop.call_later(0.5, wakeup)

        if log.getEffectiveLevel() == logging.DEBUG:
            # On debug version we enable info that
            # coroutine is not called in a way await/await
            loop.set_debug(True)

        # connect to the database
        # await connect_to_db(app)

        await Controller.instance().start()
        # Because with a large image collection
        # without md5sum already computed we start the
        # computing with server start

        from gns3server.compute.qemu import Qemu
        asyncio.ensure_future(Qemu.instance().list_images())

        for module in MODULES:
            log.debug("Loading module {}".format(module.__name__))
            m = module.instance()
            m.port_manager = PortManager.instance()

    return start_app


def create_shutdown_handler(app: FastAPI) -> Callable:

    async def shutdown_handler() -> None:
        await HTTPClient.close_session()
        await Controller.instance().stop()

        for module in MODULES:
            log.debug("Unloading module {}".format(module.__name__))
            m = module.instance()
            await m.unload()

        if PortManager.instance().tcp_ports:
            log.warning("TCP ports are still used {}".format(PortManager.instance().tcp_ports))

        if PortManager.instance().udp_ports:
            log.warning("UDP ports are still used {}".format(PortManager.instance().udp_ports))

        # close the connection to the database
        # await close_db_connection(app)

    return shutdown_handler
