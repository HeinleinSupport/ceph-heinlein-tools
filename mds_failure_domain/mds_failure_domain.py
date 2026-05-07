#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

#
# Fail standby-replay MDS if in the same failure domain as its active MDS
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

failure_domain_type="room"
ceph_config='/etc/ceph/ceph.conf'
ceph_client='client.admin'

import rados
import json
from treelib import Tree

class RadosCMD(rados.Rados):
    def command_mon(self, cmd, params=None):
        data = {'prefix': cmd, 'format': 'json'}
        if params:
            data.update(params)
        return self.mon_command(json.dumps(data), b'', timeout=5)
    def command_mgr(self, cmd):
        return self.mgr_command(json.dumps({'prefix': cmd, 'format': 'json'}), b'', timeout=5)
    def command_osd(self, osdid, cmd):
        return self.osd_command(osdid, json.dumps({'prefix': cmd, 'format': 'json'}), b'', timeout=5)
    def command_pg(self, pgid, cmd):
        return self.pg_command(pgid, json.dumps({'prefix': cmd, 'format': 'json'}), b'', timeout=5)

cluster = RadosCMD(conffile=ceph_config, name=ceph_client)
cluster.connect()

nodes = {}
root_id = None
host_ids = {}
mds_host = {}

#
# Get MDS metadata
#
res = cluster.command_mon("mds metadata")
if res[0] == 0:
    for mds_data in json.loads(res[1]):
        mds_host[mds_data["name"]] = mds_data["hostname"]

#
# Get the OSD tree (CRUSH map) and put it in a Tree structure
#

res = cluster.command_mon("osd tree")
if res[0] == 0:
    status = json.loads(res[1])
    for node in status["nodes"]:
        nodes[node["id"]] = node
        if node["type"] == "root":
            # remember root node. TODO: handle multiple root buckets
            root_id = node["id"]
        if node["type"] == "host":
            # remember IDs for hosts' names
            host_ids[node["name"]] = node["id"]
            
crush_map = Tree()

def add_to_crush_map(crush_map: Tree, nodes, id: str, parent_id=None):
    if nodes[id]["type"] != "osd":
        crush_map.create_node(nodes[id]["type"] + "=" + nodes[id]["name"], id, parent_id, nodes[id])
        for child_id in nodes[id].get("children", []):
            add_to_crush_map(crush_map, nodes, child_id, id)

if root_id:
    add_to_crush_map(crush_map, nodes, root_id)

print(crush_map.show(stdout=False))

#
# Get filesystems 
#

filesystems = {}

res = cluster.command_mon("mds stat")
if res[0] == 0:
    status = json.loads(res[1])
    for fsinfo in status["fsmap"]["filesystems"]:
        fsname = fsinfo["mdsmap"]["fs_name"]
        filesystems[fsname] = {}
        for mdsgid, mdsinfo in fsinfo["mdsmap"]["info"].items():
            if mdsinfo["rank"] not in filesystems[fsname]:
                filesystems[fsname][mdsinfo["rank"]] = {}
            filesystems[fsname][mdsinfo["rank"]][mdsinfo["state"]] = mdsinfo["name"]

#
# Check ranks for each filesystems for standby-replay MDS
#

def get_failure_domain(crush_map: Tree, host_ids, mds: str, mds_host, failure_domain_type: str):
    # hostname is the MDS name's second part. TODO: always?
    host = mds_host[mds]
    host_id = host_ids.get(host)
    for node_id in crush_map.rsearch(host_id):
        bucket = crush_map.get_node(node_id)
        if bucket.data["type"] == failure_domain_type:
            return bucket.data["name"]
    return None

for fs, ranks in filesystems.items():
    for rank, mdsinfo in ranks.items():
        if "up:standby-replay" in mdsinfo and "up:active" in mdsinfo:
            active = mdsinfo["up:active"]
            active_fd = get_failure_domain(crush_map, host_ids, active, mds_host, failure_domain_type)
            standby = mdsinfo["up:standby-replay"]
            standby_fd = get_failure_domain(crush_map, host_ids, standby, mds_host, failure_domain_type)
            print(standby, standby_fd)
            print(active, active_fd)
            if active_fd == standby_fd and standby_fd:
                print(f"Failing {standby}")
                print(cluster.command_mon("mds fail", params={"role_or_gid": standby}))

