# Installation of Samba CTDB on Ceph

This document describes the installation of a number of Samba-CTDB-Gateways in front of a Ceph cluster that serves a CephFS.

Distribution is Ubuntu 19.04 with Samba 4.10 packages.

## Installation of necessary packages

	apt install ceph-common smbclient samba ctdb winbind libnss-winbind libpam-winbind krb5-user quota
	
	systemctl stop smbd.service nmbd.service winbind.service
	
	systemctl disable smbd.service nmbd.service winbind.service

The latter three services will be started by ctdbd and not systemd.

## Mount CephFS

	echo "mon1:6789,mon2:6789,mon3:6789:/	/mnt/cephfs	ceph	_netdev,name=cephfs,secretfile=/etc/ceph/ceph.client.cephfs.secret 0 0" >> /etc/fstab

Put the secret key for client.cephfs in the file `/etc/ceph/ceph.client.cephfs.secret`.

	mkdir /mnt/cephfs

	mount /mnt/cephfs

## Configuration of CTDB

### ctdb.service unit

The ctdb.service unit needs an override. Place the following contents in `/etc/systemd/system/ctdb.service.d/override.conf`:

	[Unit]
	After=mnt-cephfs.mount
	RequiresMountsFor=/mnt/cephfs
	
	[Service]
	ExecStartPre=/bin/mkdir -p /run/ctdb

There are two bug reports open: [No /run/ctdb directory](https://bugs.launchpad.net/ubuntu/+source/ctdb/+bug/1821775) and [No /var/lib/ctdb directories](https://bugs.launchpad.net/ubuntu/+source/ctdb/+bug/1828799)

The following directories have to be created:

	mkdir -p /var/lib/ctdb/volatile
	mkdir /var/lib/ctdb/persistent
	mkdir /var/lib/ctdb/state

### ctdb.conf

The ctdb.conf file contains the recovery lock location in the cluster section. This has to be a file on the shared CephFS:

	[cluster]
		recovery lock = /mnt/cephfs/ctdb/lock

Create the necessary directory

	mkdir /mnt/cephfs/ctdb

### nodes

The file `/etc/ctdb/nodes` contains all node IPs (i.e. host IPs). E.g.:

	192.168.1.1
	192.168.1.2
	192.168.1.3

### public_addresses

The file `/etc/ctdb/public_addresses` contains the list of service IPs (same amount as node IPs) and the network mask and interfaces they should be applied to:

	192.168.1.11/24  eth0
	192.168.1.12/24  eth0
	192.168.1.13/24  eth0

The public addresses need to be put into the DNS services for the domain as multiple A records for the name of the fileserver cluster. This creates a round-robin DNS entry which load-balances the clients across the nodes.

### smb.conf

With CTDB all Samba configuration is stored in the clustered databases. The file `/etc/samba/smb.conf` only contains:

	[global]
		clustering = yes
		include = registry

### script.options

The file `/etc/ctdb/script.options` needs to contain the line:

	CTDB_SAMBA_SKIP_SHARE_CHECK=yes
	
### Enable CTDB events scripts

	ctdb event script enable legacy 49.winbind
	
	ctdb event script enable legacy 50.samba

## Start CTDB

	systemctl enable ctdb.service
	
	systemctl start ctdb.service

## Configure Samba

Samba is now configured with `net conf` and first needs a working `[global]` section:

	[global]
		server role = MEMBER SERVER
		workgroup = EXAMPLE
		security = ads
		realm = EXAMPLE.COM
		netbios name = FILESERV
		netbios aliases = FILESERV NODE1 NODE2 NODE3
		winbind use default domain = yes
		winbind refresh tickets = yes
		idmap config * : backend = tdb
		idmap config * : range = 2000-9999
		idmap config EXAMPLE : backend = rid
		idmap config EXAMPLE : range = 10000-200000
		template shell = /bin/bash
		preferred master = No
		local master = No
		domain master = No
		max log size = 50
		vfs objects = acl_xattr
		map acl inherit = Yes
		store dos attributes = Yes
		kerberos method = secrets and keytab
		usershare path = 
		load printers = No
		printcap name = /dev/null
		log level = 3
		
The idmap backend for the domain may have to be changed accordingly. The whole section can be imported with `net conf import`.

### Join Domain

Now the cluster can be joind as member to the domain

	net ads join {-U username}

	service ctdb restart

	wbinfo -t

### PAM & NSS

Add `winbind` to the `passwd` and `group` lines of `/etc/nsswitch.conf`.

`pam-auth-update` can be used to enable or disable certain PAM modules.

### Samba Shares

The Samba VFS module for Ceph can be used to access the CephFS directly from the Samba process without going through the kernel mount. The path is then starting at the root of the CephFS and not the root of the node's filesystem. A share section should contain these lines in addition to other parameters for the share:

	[sharename]
		path = /export/sharename
		kernel share modes = no
		vfs objects = ceph
		ceph:user_id = cephfs

The directory for the share has to be created:

	mkdir -p /mnt/cephfs/export/sharename
	
E.g. /mnt/cephfs is the mount point of the CephFS at the nodes and therefor the root directory for the share paths.
	
Samba needs `/etc/ceph/ceph.conf` to know about the monitors and the keyring file for the client.cephfs in `/etc/ceph/ceph.client.cephfs.keyring`.

## net conf

`net conf` is the CLI tool to edit the Samba configuration in a CTDB setup.

### Usage

	net conf list            Dump the complete configuration in smb.conf like format.
	net conf import          Import configuration from file in smb.conf format.
	net conf listshares      List the share names.
	net conf drop            Delete the complete configuration.
	net conf showshare       Show the definition of a share.
	net conf addshare        Create a new share.
	net conf delshare        Delete a share.
	net conf setparm         Store a parameter.
	net conf getparm         Retrieve the value of a parameter.
	net conf delparm         Delete a parameter.
