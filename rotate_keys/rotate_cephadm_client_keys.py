#!/usr/bin/env python3

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

import rados
import json
from pprint import pprint

ceph_config='/etc/ceph/ceph.conf'
ceph_client='client.admin'

class RadosCMD(rados.Rados):
    def command_mon(self, cmd, params=None):
        data = {'prefix': cmd, 'format': 'json'}
        if params:
            data.update(params)
        return self.mon_command(json.dumps(data), b'', timeout=5)

cluster = RadosCMD(conffile=ceph_config, name=ceph_client)
cluster.connect()

res = cluster.command_mon("orch ps")
if res[0] == 0:
    daemons = list(map(lambda x: x.get("daemon_name"), json.loads(res[1])))

res = cluster.command_mon("health", params={'detail': 'detail'})
if res[0] == 0:
    health_detail = json.loads(res[1])
    insecure_clients = health_detail.get("checks", {}).get("AUTH_INSECURE_CLIENT_KEY_TYPE", {}).get("detail", [])
    for client in insecure_clients:
        client_name = client.get("message", "").split(" ")[1]
        if client_name.startswith("client."):
            if client_name[7:] in daemons:
                print(f"ceph auth rotate --key-type=aes256k {client_name}")
                print(f"ceph orch daemon redeploy {client_name[7:]}")
            if client_name[7:17] == "bootstrap-":
                print(f"ceph auth rotate --key-type=aes256k {client_name}")
