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

channel = readJson(sys.argv[1])

if channel != None:
    print "Name: "+channel['name']
    for m in channel['messages']:
        print m['ts']+": "+m['text']
else:
    print "Channel not found"
