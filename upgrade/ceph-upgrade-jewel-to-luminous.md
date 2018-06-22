# Ceph Upgrade jewel to luminous

## 1. Upgrade Software to new Version

	admin-node:$ cd deploydirectory
	admin-node:$ ceph-deploy install --release luminous node[ node[ node]]


## 2. Restart mons

	admin-node:$ for host in node[ node[ node]]; do ssh root@$host "systemctl restart ceph-mon@${host}.service"; sleep 5; done

## 3. Verify running mons


	cluster:
	  id:     418cfef5-e61a-40ed-a114-44debf0a2acf
	  health: HEALTH_OK
 	  
	services:
	  mon: 3 daemons, quorum ceph01,ceph02,ceph03
	  mgr: no daemons active
	  mds: fs-1/1/1 up  {0=mds02=up:active}, 2 up:standby
	  osd: 6 osds: 6 up, 6 in
	  
## 4. Install missing MGR components (at least 2)

	admin-node:$ ceph-deploy mgr create node [2nd node]


## 5. Verify running MGR



	  cluster:
	    id:     418cfef5-e61a-40ed-a114-44debf0a2acf
	    health: HEALTH_OK
	 
	  services:
	    mon: 3 daemons, quorum ceph01,ceph02,ceph03
	    mgr: ceph01(active), standbys: ceph02, ceph03
	    mds: fs-1/1/1 up  {0=mds02=up:active}, 2 up:standby
	    osd: 6 osds: 6 up, 6 in
	

## 6. enable MGR dashboard (optional)

	node:# ceph mgr module enable dashboard

## 7. Verify dashboard


	node:# ceph mgr module ls
	{
	    "enabled_modules": [
	        "balancer",
	        "dashboard",
	        "restful",
	        "status"
	    ],
	    "disabled_modules": [
	        "influx",
	        "localpool",
	        "prometheus",
	        "selftest",
	        "zabbix"
	    ]
	}

	node:# ceph mgr services
	{
	    "dashboard": "http://ceph01.test.heinlein-intern.de:7000/"
	}



## 8. restart every mds

## 9. restart every osd (or migrate during this step to bluestore)

## add application to every pool

	node:# ceph osd pool application enable pool_name_for_block_devices rbd
	node:# ceph osd pool application enable pool_name_for_custom_application mything
	node:# ceph osd pool application enable pool_name_for_rados_obtects rgw


---

# Delete a pool with ceph luminous

To remove a pool, it's necessary since luminous to tell the MON to allow pool deletion.

	node:# ceph tell mon.\* injectargs '--mon-allow-pool-delete=true'
	node:# ceph osd pool rm pool_name pool_name --yes-i-really-really-mean-it
	node:# ceph tell mon.\* injectargs '--mon-allow-pool-delete=false'


---

# Device classes since ceph luminous

## Tag the device with the matching class

If autonegotiation of device class fails, put a device into the correct class.

	node:# ceph osd crush rm-device-class osd.N
	node:# ceph osd crush set-device-class [ssd|hdd] osd.N

## List devices tagged with a particular class

	node:# ceph osd crush class ls-osd [ssd|hdd]



