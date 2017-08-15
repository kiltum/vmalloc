#!/usr/bin/env python

import atexit
import requests
import ssl
import sys
import time
from tools import cli
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
from array import array


# disable  urllib3 warnings
if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

# http://stackoverflow.com/questions/1094841/
def sizeof_fmt(num):
    """
    Returns the human readable version of a file size

    :param num:
    :return:
    """
    for item in ['B', 'KB', 'MB', 'GB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, item)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')



def get_args():
    parser = cli.build_arg_parser()
    parser.add_argument('-n', '--name', required=False,
                        help="Move only from this Datastore.")
    parser.add_argument('-d', '--destination', required=False,
                        help="Migrate only to this datastore mask")
    parser.add_argument('-t', '--target', required=False,
                        help="Take only this VM mask")
    parser.add_argument('-l', '--limit', required=False,
                        help="Do not touch datastores with free percentage above this limit. By default 11%%")
    parser.add_argument('-v', '--verbose', required=False, action='store_true',
                        help="Show what doing now.")
    my_args = parser.parse_args()
    return cli.prompt_for_password(my_args)

args = get_args()

ds_list = [] # datastore 

dc_to_check = ""
dc_limit = 11
dc_target = ""
dc_dest = ""

ds_from = [] # stor from waht will be migrate
ds_to = [] # destination stor
ds_to_free = [] # percent free AFTER possible migration (do no trecalculate)
vm_to = [] # VM to move

bad_stor_exist = False


def wait_for_task(task):
    while True:
        if task.info.state == vim.TaskInfo.State.success:
            return
        if task.info.state == vim.TaskInfo.State.error:
            raise Exception('task failed')
        time.sleep(1)
        sys.stdout.write(". ")
        sys.stdout.flush()
               
def main():
    global dc_to_check, dc_limit, dc_target, bad_stor_exist , dc_dest, vm_to

    if args.verbose:
        sys.stdout.write("Connect to VMWare ... ")
        sys.stdout.flush()
        
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    if args.disable_ssl_verification:
        context.verify_mode = ssl.CERT_NONE
    
    
    si = SmartConnect(
        host=args.host,
        user=args.user,
        pwd=args.password,
        port=args.port, sslContext=context)
    # disconnect vc
    atexit.register(Disconnect, si)
    if args.verbose:
        print "Connected!"
    content = si.RetrieveContent()

    datacenter = content.rootFolder.childEntity[0]
    datastores = datacenter.datastore
    
    
    if args.name:
        dc_to_check = args.name
 
    if args.target:
        dc_target = args.target

    if args.destination:
        dc_dest = args.destination

    if args.limit:
        dc_limit = int (args.limit)

    #ds_collect(datastores)

    ds_list = []

    need_free = 0

    for ds in datastores:
        if dc_to_check in ds.summary.name:
            ds_list.append(ds)
            if args.verbose:
                print "Found %s" % ds.summary.name

    for i, ds in enumerate(ds_list):
        need_perc = dc_limit - ((ds.summary.freeSpace * 100) / ds.summary.capacity) + 1
        need_free = (ds.summary.capacity/100) * need_perc
        if(need_perc > 0):
            print "%s need to free %s" % (ds.summary.name, sizeof_fmt(need_free))
            bad_stor_exist = True
            # now try to find stor with free space
            for n,vl in enumerate(ds_list):
                # calculate, how many space left if we push 
                c = vl.summary.freeSpace - need_free
                p = (c * 100) / vl.summary.capacity
                if(p>dc_limit):
                    if args.verbose:
                        print "%s will have %s%% free. good" % (vl.summary.name, p)
                    if dc_dest in vl.summary.name:
                        ds_from.append(ds)
                        ds_to.append(vl)
                        ds_to_free.append(p)
                        if args.verbose:
                            print "Can move %s -> %s" % (ds.summary.name,vl.summary.name)
                    else:
                        if args.verbose:
                            print "Cannot %s /> %s (banned by destination)" % (ds.summary.name,vl.summary.name)
                else:
                    if args.verbose:
                        print "%s not suitable %s%%<%s%% bad" % (vl.summary.name, p, dc_limit)
                # ok, now we need to collect VM files

    if bad_stor_exist == True:
        print "Found %s possible relocations" % len(ds_from)
        if len(ds_from) == 0:
            print "ALERT! Lack of space. Do handjob quickly ..."
            return # noting to do
        # ok, lets choice which stor
        ch_n = 0
        ch_p = 0
        for i,fr in enumerate(ds_from):
            print "Can migrate %s -> %s" % (fr.summary.name, ds_to[i].summary.name)
            if ds_to_free[i] > ch_p:
                ch_n=i
                ch_p=ds_to_free[i]
        print "OK, lets move from %s to %s (%s%% free will be after move)" % (ds_from[ch_n].summary.name, ds_to[ch_n].summary.name, ch_p)
        # now select VM to move.
        print "Try to find possible VM to move"

        np = dc_limit - ((ds_from[ch_n].summary.freeSpace * 100) / ds_from[ch_n].summary.capacity) + 1
        nf = (ds_from[ch_n].summary.capacity/100) * np

        for i,vm in enumerate(ds_from[ch_n].vm):
            s = 0    
            for t in vm.layoutEx.file: 
                s=s+t.size
            
            if dc_target in vm.summary.config.name:
                if args.verbose:
                    print "Can take %s (%s)" % (vm.summary.config.name , sizeof_fmt(s))
                # collect enougth VM to move
                if nf > 0 :
                    vm_to.append (vm)
                    nf = nf - s
            else:
                if args.verbose:
                    print "Cannot take %s (banned by target) %s " % (vm.summary.config.name, sizeof_fmt(s))
        if len(vm_to) == 0:
            print "ALERT! Ooops, cannot find VM to move. Abort"
            return

        for i,vm in enumerate(vm_to):
            print "Ok, Final. Move %s from %s to %s " % (vm.summary.config.name,ds_from[ch_n].summary.name, ds_to[ch_n].summary.name)
            # https://gist.github.com/rgerganov/12fdd2ded8d80f36230f
            # vm = vim.VirtualMachine(vm.summary.config.name, si._stub)
            
            disk_key = []
            disk_filekey = []
            # collect info about key - filekey and grab only one part or pair (vmdk, -flat.vmdk)
            for t in vm.layoutEx.disk:
                disk_key.append(t.key)
                disk_filekey.append(t.chain[0].fileKey[0])
                #print "DISK ", t.key, t.chain[0].fileKey[0]
            # check disk for moving
            for t in vm.layoutEx.file:
                #print "Check %s " % t.name 
                if ds_from[ch_n].summary.name in t.name: # ok this file on bad store, move
                    for i, j in enumerate(disk_filekey):
                        # print "compare %s %s" % (j,t.key)
                        if j == t.key:
                            spec = vim.VirtualMachineRelocateSpec()

                            dsk = vim.VirtualMachineRelocateSpecDiskLocator()

                            print "Move %s queue" % t.name
                            dsk.datastore = ds_to[ch_n]
                            dsk.diskId = disk_key[i]
                            spec.disk.append(dsk)
                            task = vm.RelocateVM_Task(spec)
                            wait_for_task(task)

                else:
                    print "%s already moved" % t.name

    else:
        print "All look seems to be in order. Have a nice day!"

        
        

# start
if __name__ == "__main__":
    main()

