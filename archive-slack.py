#!/usr/bin/python

# $Id: archive-slack.py,v 1.6 2015/05/11 08:15:55 errror Exp $

import requests, httplib, json, pprint, sys, os, getopt

# generic wrapper for slack api calls, error handling only basic
def slackApi(function, args = {}):
    uri = '/api/'+function+'?token='+token
    for a in args:
        uri += '&'+a+'='+args[a]
    result = None
    try:
        hcon.request('GET', uri)
        result = hcon.getresponse()
    except (httplib.BadStatusLine), ex:
        # this happens sometimes, we retry once
        try:
            hcon.request('GET', uri)
            result = hcon.getresponse()
        except (httplib.BadStatusLine), ex:
            print 'Error fetching "%s" from Slack: %s' % (url, str(ex))
            raise ex
    raw_data = result.read()
    try:
        return json.loads(raw_data)
    except:
        print "Error decoding answer from slack API call %s (raw_data=%s)" % (function, raw_data)
        raise

# loads the list of all users with their attributes
def getUsers():
    json = slackApi('users.list')
    users = {}
    for i in json['members']:
        users[i['id']] = i
    return users

# loads the list of all channels with their attributes
def getChannels():
    json = slackApi('conversations.list', args = {
        'exclude_archived': 'true',
        'types': 'public_channel',
    })
    channels = {}
    if not 'channels' in json:
        pprint.pprint(json)
    for i in json['channels']:
        channels[i['id']] = i
    return channels

# loads the list of all groups with their attributes
def getGroups():
    json = slackApi('conversations.list', args = {
        'exclude_archived': 'true',
        'types': 'private_channel',
    })
    groups = {}
    for i in json['channels']:
        groups[i['id']] = i
    return groups

# loads the list of all direct message channels with their attributes
def getDMs():
    json = slackApi('conversations.list', args = {
        'exclude_archived': 'true',
        'types': 'im',
    })
    ims = {}
    for i in json['channels']:
        ims[i['id']] = i
    return ims

# writes a json output file 'name.json' containing json serialization of 'data'
def writeJson(name, data, subdir = "."):
    f = open(subdir+os.sep+name+'.json', 'w')
    f.write(json.dumps(data))
    f.close()

# reads a json input file 'name.json' returning deserialized data
def readJson(name, subdir = "."):
    if os.path.isfile(subdir+os.sep+name+'.json'):
        f = open(subdir+os.sep+name+'.json', 'r')
        raw_data = f.read()
        try:
            data = json.loads(raw_data)
        except:
            print "Error while loading name=%s (raw_data=%s)" % (name, raw_data)
            sys.exit(1)
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
        json = slackApi('conversations.history',{
            'channel': id,
            'count': '1000',
            'latest': str(latest),
            'oldest': str(last_ts),
            })
        try:
            has_more = json['has_more']
        except KeyError as e:
            print "Got KeyError while checking for has_more: %s" % str(e)
            print "Got this from slack:"
            pprint.pprint(json)
            has_more = False
        for i in json['messages']:
            oldmessages.append(i)
            latest = i['ts']
    oldmessages.sort(key = lambda msg: msg['ts'])
    return oldmessages

# loads the members of channel/group 'id',
def getChannelMembers(id):
    json = slackApi('conversations.members',{
            'channel': id,
            'limit': '1000',
            })
    try:
        return json['members']
    except KeyError:
        return []
    
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
        channels[c]['members'] = getChannelMembers(c)
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
        try:
            pages = int(json['paging']['pages'])
        except KeyError as e:
            pprint.pprint(json)
            raise e
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
        download_url = ''
        if f.has_key('url_download'):
            download_url = f['url_download']
        elif f.has_key('url_private_download'):
            download_url = f['url_private_download']
        elif f.has_key('permalink'):
            download_url = f['permalink']
        else:
            pprint.pprint(f)
            print 'Error: Could not find suitable url to download this file'
            return
        req = requests.get(download_url, headers={'Authorization': 'Bearer %s' % token})
        if req.status_code != 200:
            print 'Error fetching file '+f['id']+' from '+download_url
            print 'status_code: %s' % req.status_code
        else:
            out = open(outfilename, 'w')
            out.write(req.content)
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
