#!/usr/bin/python

# $Id: archive-slack.py,v 1.4 2015/02/26 12:38:22 errror Exp $

# apt-get install python-anyjson
import httplib, anyjson, pprint, sys, os, getopt

# generic wrapper for slack api calls, error handling only basic
def slackApi(function, args = {}):
    uri = '/api/'+function+'?token='+token
    for a in args:
        uri += '&'+a+'='+args[a]
    hcon.request('GET', uri)
    result = hcon.getresponse()
    if result.status != 200:
        print 'Error '+function+'(): '+result.status+' ('+result.reason+')'
        exit(1)
    return anyjson.deserialize(result.read())

# loads the list of all users with their attributes
def getUsers():
    json = slackApi('users.list')
    users = {}
    for i in json['members']:
        users[i['id']] = i
    return users

# loads the list of all channels with their attributes
def getChannels():
    json = slackApi('channels.list')
    channels = {}
    for i in json['channels']:
        channels[i['id']] = i
    return channels

# loads the list of all groups with their attributes
def getGroups():
    json = slackApi('groups.list')
    groups = {}
    for i in json['groups']:
        groups[i['id']] = i
    return groups

# loads the list of all direct message channels with their attributes
def getDMs():
    json = slackApi('im.list')
    ims = {}
    for i in json['ims']:
        ims[i['id']] = i
    return ims

# writes a json output file 'name.json' containing json serialization of 'data'
def writeJson(name, data, subdir = "."):
    f = open(subdir+os.sep+name+'.json', 'w')
    f.write(anyjson.serialize(data))
    f.close()

# reads a json input file 'name.json' returning deserialized data
def readJson(name, subdir = "."):
    if os.path.isfile(subdir+os.sep+name+'.json'):
        f = open(subdir+os.sep+name+'.json', 'r')
        data = anyjson.deserialize(f.read())
        f.close()
        return data
    else:
        return None

# loads the complete available history of channel/group 'id',
# type must be 'channel' or 'group'
# 'oldmessages' can be a list of already fetched messages
def getHistory(id, type, oldmessages):
    has_more = True
    latest = 0
    last_ts = 0
    if len(oldmessages) > 0:
        last_ts = oldmessages[-1]['ts']
    while has_more:
        json = slackApi(type+'.history',{
            'channel': id,
            'count': '1000',
            'latest': str(latest),
            'oldest': str(last_ts),
            })
        has_more = json['has_more']
        for i in json['messages']:
            oldmessages.append(i)
            latest = i['ts']
    oldmessages.sort(key = lambda msg: msg['ts'])
    return oldmessages

# iterate over all channels/groups given as 'channels' dict,
# fetches their complete history and writes them to a json file,
# type must be 'channel' or 'group'
def fetchChannels(channels, type, subdir):
    if not os.path.isdir(subdir):
        os.mkdir(subdir)
    for c in channels:
        name = ''
        if type == 'im':
            name = channels[c]['user']
            if name != 'USLACKBOT':
                name = users[name]['name']
        else:
            name = channels[c]['name']
        verboseprint("  "+name)
        oldchannel = readJson(c, subdir)
        oldmessages = []
        if oldchannel != None:
            oldmessages = oldchannel['messages']
        channels[c]['messages'] = getHistory(c, type, oldmessages)
        writeJson(c, channels[c], subdir)

# loads the list of all files with all their attributes
def getFiles():
    page = 1
    pages = 2
    files = []
    while page < pages:
        json = slackApi('files.list',{
            'count': '1000',
            'page': str(page),
            })
        pages = int(json['paging']['pages'])
        page += 1
        for i in json['files']:
            files.append(i)
    return files

# iterate over all files given as 'files' array,
# fetches their complete history and writes them to a json file,
def fetchFiles(files, oldfiles):
    oldfiledict = {}
    if oldfiles != None:
        for f in oldfiles:
            oldfiledict[f['id']] = f
    for f in files:
        if len(f['channels']) == 0 and len(f['groups']) == 0 and not private:
            verboseprint("  "+f['name']+" (private)")
            continue
        if f['filetype'] == 'gdoc':
            verboseprint("  "+f['name']+" (GDoc)")
            continue
        if f['filetype'] == 'gsheet':
            verboseprint("  "+f['name']+" (GSheet)")
            continue
        if f['filetype'] == 'gpres':
            verboseprint("  "+f['name']+" (GPresentation)")
            continue
        if not os.path.isdir('files'):
            os.mkdir('files')
        outfilename = 'files'+os.sep+f['id']+'.'+f['filetype'];
        if os.path.isfile(outfilename) and oldfiledict.has_key(f['id']):
            verboseprint("  "+f['name']+" (already downloaded)")
            continue
        if oldfiledict.has_key(f['id']) and f['timestamp'] == oldfiledict[f['id']]['timestamp']:
            infoprint("  "+f['name']+" (modified, redownloading)")
        else:
            infoprint("  "+f['name'])
        hcon = httplib.HTTPSConnection('slack-files.com')
        if not f.has_key('url_download'):
            pprint.pprint(f)
        hcon.request('GET', f['url_download'][23:])
        result = hcon.getresponse()
        if result.status != 200:
            print 'Error fetching file '+f['id']+' from '+f['url_download']
        else:
            out = open(outfilename, 'w')
            out.write(result.read())
            out.close()

def usage(exitcode):
    print ""
    print "Usage: archive-slack.py [options] <auth-token>"
    print ""
    print "Options:"
    print "    -h --help      : print this help"
    print "    -q --quiet     : no output except errors"
    print "    -v --verbose   : verbose output"
    print "    -p --no-public : skip download of public channels, private groups and files"
    print "    -P --private   : include direct messages and private files"
    print ""
    print "Use https://api.slack.com/#auth to generate your auth-token."
    exit(exitcode)

def verboseprint(text):
    if verbose:
        print text.encode('ascii', 'ignore')

def infoprint(text):
    if not quiet:
        print text.encode('ascii', 'ignore')

#
# main
#

# for all api calls, we need a https connection to slack.com
hcon = httplib.HTTPSConnection('slack.com')
opts, args = getopt.gnu_getopt(sys.argv,
                               'hqvpP',
                               [
                                   'help',
                                   'quiet',
                                   'verbose',
                                   'no-public',
                                   'private',
                                   ])
# and a authentication token, given via cmdline arg, use https://api.slack.com/#auth to generate your own
if len(args) != 2:
    usage(1)
token = args[1]

quiet = False
verbose = False
nopublic = False
private = False

for o, v in opts:
    if o == '--help' or o == '-h':
        usage(0)
    elif o == '--quiet' or o == '-q':
        quiet = True
    elif o == '--verbose' or o == '-v':
        verbose = True
    elif o == '--no-public' or o == '-p':
        nopublic = True
    elif o == '--private' or o == '-P':
        private = True
    else:
        usage(1)

# verbose overrides quiet
if verbose:
    quiet = False

if not nopublic or private:
    users = getUsers()
if not nopublic:
    writeJson('users', users)
    infoprint("Channels")
    channels = getChannels()
    writeJson("channels", channels)
    fetchChannels(channels, 'channels', 'channels')
    infoprint("Groups")
    groups = getGroups()
    writeJson("groups", groups)
    fetchChannels(groups, 'groups', 'groups')
    infoprint("Files")
    files = getFiles()
    oldfiles = readJson('files')
    fetchFiles(files, oldfiles)
    writeJson('files', files)
if private:
    infoprint("DMs")
    fetchChannels(getDMs(), 'im', 'dms')
