#! /bin/bash
#
# this script aims to be a helping hand for migrating ceph OSD using filestore to
# migrate to bluestore. There is no magic A.I. against data loss built in!
#
# Usage:   ./migrate_to_bluestore.sh NUMERIC_OSD_ID_RUNNING_ON_THIS_PARTICULAR_HOST
# Example: ./migrate_to_bluestore.sh 12 # if osd.12 is running on THIS host.
#
# WARNING!
# The originating OSD are assumed to
# - have the journal on the same block device than the data
# - are exclusively without any related or unrelated stuff on a block device
#
# The resulting OSD will
# - have the very same ceph authentication keyring
# - be running bluestore including WAL and RocksDB exclusively on the very same
#   block device, the originating OSD was running on.
#
# ### IF YOU CAN NOT CHECK EVERY PRIOR LINE - DO NOT USE THIS SCRIPT ###
#
# but, otherwise, if you're happy with that: Keep in mind
# - you shouldn't exceed through all OSD without monitoring your ceph health
# - at one particular point of no return, you have to press ENTER to continue :)
#
# Currently, and with the prior noted limitations in mind, every single operation
# is double checked to avoid wild behaviour.
#
# And as always: USE AT YOUR OWN RISK
#
# First public release
#	2018-06-19 Stephan Seitz <s.seitz@heinlein-support.de>
#
#

this=$(basename $0)
export this

LC_ALL=C
export LC_ALL

verbose() {
	echo "$@" >/dev/stderr
}

ok() {
	verbose "[ok] $@"
}

warn() {
	verbose "[warn] $@"
}

fail() {
	verbose "[fail] $@"
}

inf() {
	verbose "[info] $@"
}

if [ -x $1 ]
then
	verbose "Usage: ${this} NUMERIC_OSD_ID_RUNNING_ON_THIS_PARTICULAR_HOST"
	exit 5
fi

ID=$1
export ID

if [ $(ceph osd tree | grep "osd.${ID} " | wc -l) -eq 0 ]
then
	fail "osd.${ID} does not exist in this ceph cluster. Exiting."
	exit 5
fi


if [ $(systemctl list-units | grep ceph-osd@${ID}.service | wc -l) -eq 0 ]
then
	fail "osd.${ID} is not running on this host. Exiting."
	exit 5
fi


# Results in FILE or BLUE
current_store=$(ceph osd metadata ${ID} | awk '/osd_objectstore/{ print toupper(substr($2, 2, 4 )); }')
if [ "_${current_store}" == "_BLUE" ]
then
	verbose "osd.${ID} is already running with bluestore. Nothing to do. Exiting."
	exit 1
elif [ "_${current_store}" != "_FILE" ]
then
	verbose "osd.${ID} is not filestore and not bluestore. Bailing."
	exit 10
fi


ok " osd.${ID} is running on this host."
ok "osd.${ID} is formatted with filestore."

# 1. ceph osd out ID
ceph osd out ${ID}
RC=$?
if [ $RC -gt 0 ]
then
	fail "ceph osd out ${ID}"
	verbose "Exiting. It's up to you to resolve this issue. Sorry"
	exit 20
else
	ok "ceph osd out ${ID}"
fi
sleep 1

# 2. systemctl stop ceph-osd@ID.service
# 2. systemctl kill ceph-osd@ID.service

systemctl stop ceph-osd@${ID}.service
systemctl kill ceph-osd@${ID}.service
verbose "[ok] systemctl kill ceph-osd@${ID}.service"

# 3. Get device and mountpoint
mountline=$(mount | grep "/var/lib/ceph/osd/ceph-${ID} ")
assumed_partition=$(echo "${mountline}" | awk '{ print $1; }' | sed 's,^/dev/,,g')
assumed_mountpoint=$(echo "${mountline}" | awk '{ print $3; } ')
assumed_device=/dev/$(find -L /sys/block/  -mindepth 2 -maxdepth 2 -type d -name ${assumed_partition} | \
	sed 's,^/sys/block/,,g;s,/'${assumed_partition}'$,,g')

assumed_partition="/dev/${assumed_partition}"

inf "osd.${ID} has ${assumed_partition} on device ${assumed_device} mounted on ${assumed_mountpoint}"

# 3b. double check
# - Test if the resulting device is indeed a block special device"
if [ $(stat -c "%F" ${assumed_device} | grep -i 'block' | wc -l) -eq 1 ]
then
	inf "Device ${assumed_device} for osd.${ID} is verified as block device. good."
else
	fail "Underlaying device ${assumed_device} obviously for osd.${ID} is NOT a block device. Bailing."
	exit 20
fi
# - Test if we find the partition and the mountpoint again in the mountline (just double check)
if [ $(mount | grep "${assumed_partition}" | grep "${assumed_mountpoint}" | wc -l) -eq 1 ]
then
	inf "Just double checked if ${assumed_partition} is really mounted on ${assumed_mountpoint}. good."
else
	fail "Double checked and did not find ${assumed_partition} mounted on ${assumed_mountpoint}. Bailing."
	exit 20
fi

umount ${assumed_mountpoint}
RC=$?
if [ $RC -gt 0 ]
then
	fail "Unable to unmount ${assumed_mountpoint}. This should not happen. Bailing."
	exit 20
else
	ok "umount ${assumed_mountpoint}"
fi

verbose "#### UNTIL HERE, EVERYTHINGS HARMLESS AND REVERTABLE. HIT CTRL-C TO ABORT - OR ENTER TO MOVE ON. ####"
read keystroke

result=0

ceph-volume lvm zap ${assumed_device}
RC=$?
if [ $RC -gt 0 ]
then
	fail "ceph-volume lvm zap ${assumed_device} - anyway we try to continue..."
	result=$[result+1]
else
	ok "ceph-volume lvm zap ${assumed_device}"
fi

ceph osd destroy ${ID} --yes-i-really-mean-it
RC=$?
if [ $RC -gt 0 ]
then
	fail "ceph osd destroy ${ID} --yes-i-really-mean-it - anyway we try to continue..."
	result=$[result+1]
else
	ok "ceph osd destroy ${ID} --yes-i-really-mean-it"
fi

ceph-volume lvm create --bluestore --data ${assumed_device} --osd-id ${ID}
RC=$?
if [ $RC -gt 0 ]
then
	fail "ceph-volume lvm create --bluestore --data ${assumed_device} --osd-id ${ID}"
	result=$[result+1]
else
	ok "ceph-volume lvm create --bluestore --data ${assumed_device} --osd-id ${ID}"
fi


if [ $result -gt 0 ]
then
	warn "$result errors happened."
	exit 25
else
	ok "Your osd.${ID} should now be on bluestore."
fi

