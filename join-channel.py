#!/usr/bin/python

import httplib, json, pprint, sys, os, getopt

# reads a json input file 'name.json' returning deserialized data
def readJson(name):
    if os.path.isfile(name):
        f = open(name, 'r')
        data = json.loads(f.read())
        f.close()
        return data
    else:
        return None

oldmessages = {}
lastchannel = None
for f in sys.argv[1:]:
    channel = readJson(f)
    if channel != None:
        lastchannel = channel
        for m in channel['messages']:
            if not oldmessages.has_key(m['ts']):
                oldmessages[m['ts']] = m
    else:
        print "Channel not found: %s" % f

if lastchannel != None:
    keys = oldmessages.keys()
    keys.sort()

    messages = []
    for k in keys:
        messages.append(oldmessages[k])

    lastchannel['messages'] = messages
    print json.dumps(lastchannel)
else:
    print "Did not find any data for channels %s" % sys.argv[1:]
