#!/usr/bin/python

# apt-get install python-anyjson
import httplib, anyjson, pprint, sys, os, getopt

# reads a json input file 'name.json' returning deserialized data
def readJson(name):
    if os.path.isfile(name):
        f = open(name, 'r')
        data = anyjson.deserialize(f.read())
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
    print anyjson.serialize(lastchannel)
else:
    print "Did not find any data for channels %s" % sys.argv[1:]
