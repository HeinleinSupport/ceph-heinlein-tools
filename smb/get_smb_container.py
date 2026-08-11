#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

#
# Get the container name for the SMB service container from podman
#

# (c) 2026 Heinlein Support GmbH
#          Robert Sander <r.sander@heinlein-support.de>

# This is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  This file is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# ails.  You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

podman_socket="/run/podman/podman.sock"

import podman
import podman.errors

with podman.PodmanClient(base_url=f"http+unix://{podman_socket}") as client:
    if client.ping():
        containers = client.containers.list()
        for container in containers:
            if "smb" in container.name: # pyright: ignore[reportOperatorIssue]
                try:
                    info = container.inspect()
                except podman.errors.exceptions.APIError:
                    info = { "Args": [None] }
                if info["Args"][-1] == "smbd":
                    print(container.name)
