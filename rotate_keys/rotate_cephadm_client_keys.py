#!/usr/bin/env python3

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
