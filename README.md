# vmalloc

Script that re-implement DRS feature of vmware& In other words, check VMWare datastores, find which one with low free space and try to relocate VM to free datastore. But with very important features:

- Can specify datastores to free 
- Can specify datastores to use as target
- Can specify VM to touch
- Relocate one disk of VM per time.

```
usage: vmalloc.py [-h] -s HOST [-o PORT] -u USER [-p PASSWORD] [-S] [-n NAME]
                  [-d DESTINATION] [-t TARGET] [-l LIMIT] [-v]

Standard Arguments for talking to vCenter

optional arguments:
  -h, --help            show this help message and exit
  -s HOST, --host HOST  vSphere service to connect to
  -o PORT, --port PORT  Port to connect on
  -u USER, --user USER  User name to use when connecting to host
  -p PASSWORD, --password PASSWORD
                        Password to use when connecting to host
  -S, --disable_ssl_verification
                        Disable ssl host certificate verification
  -n NAME, --name NAME  Move only from this Datastore.
  -d DESTINATION, --destination DESTINATION
                        Migrate only to this datastore mask
  -t TARGET, --target TARGET
                        Take only this VM mask
  -l LIMIT, --limit LIMIT
                        Do not touch datastores with free percentage above
                        this limit. By default 11%
  -v, --verbose         Show what doing now.

```

"Mask" here - it part of name, so if i set mask to "cor", script takes core1, lacore2, etc but not touch disk-ore

 