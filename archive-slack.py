#!/usr/bin/python3
# pylint: disable=missing-function-docstring,missing-module-docstring,invalid-name

import http.client
import json
import pprint
import sys
import os
import io
# pylint: disable=deprecated-module
import getopt

import requests

USERS = {}

# generic wrapper for slack api calls, error handling only basic
def slackApi(function, args = {}): # pylint: disable=dangerous-default-value
    uri = '/api/'+function+'?token='+token
    for a in args:
        uri += '&'+a+'='+args[a]
    result = None
    try:
        hcon.request('GET', uri)
        result = hcon.getresponse()
    except http.client.BadStatusLine:
        # this happens sometimes, we retry once
        try:
            hcon.request('GET', uri)
            result = hcon.getresponse()
        except http.client.BadStatusLine as bsl:
            print(f'Error fetching "{uri}" from Slack: {bsl}')
            raise bsl
    raw_data = result.read()
    try:
        return json.loads(raw_data)
    except:
        print(f"Error decoding answer from slack API call {function} (raw_data={raw_data})")
        raise

# loads the list of all users with their attributes
def getUsers():
    users_json = slackApi('users.list')
    users = {}
    for i in users_json['members']:
        users[i['id']] = i
    return users

# loads the list of all channels with their attributes
def getChannels():
    convs_json = slackApi('conversations.list', args = {
        'exclude_archived': 'true',
        'types': 'public_channel',
    })
    channels = {}
    if not 'channels' in convs_json:
        pprint.pprint(convs_json)
    for i in convs_json['channels']:
        channels[i['id']] = i
    return channels

# loads the list of all groups with their attributes
def getGroups():
    convs_json = slackApi('conversations.list', args = {
        'exclude_archived': 'true',
        'types': 'private_channel',
    })
    groups = {}
    for i in convs_json['channels']:
        groups[i['id']] = i
    return groups

# loads the list of all direct message channels with their attributes
def getDMs():
    convs_json = slackApi('conversations.list', args = {
        'exclude_archived': 'true',
        'types': 'im',
    })
    ims = {}
    for i in convs_json['channels']:
        ims[i['id']] = i
    return ims

# writes a json output file 'name.json' containing json serialization of 'data'
def writeJson(name, data, subdir = "."):
    with io.open(subdir+os.sep+name+'.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(data))

# reads a json input file 'name.json' returning deserialized data
def readJson(name, subdir = "."):
    if os.path.isfile(subdir+os.sep+name+'.json'):
        with io.open(subdir+os.sep+name+'.json', 'r', encoding='utf-8') as f:
            raw_data = f.read()
        try:
            data = json.loads(raw_data)
        except: # pylint: disable=bare-except
            print(f"Error while loading name={name} (raw_data={raw_data})")
            sys.exit(1)
        return data
    return None

# loads the complete available history of channel/group 'id',
# type must be 'channel' or 'group'
# 'oldmessages' can be a list of already fetched messages
def getHistory(_id, _type, oldmessages):
    has_more = True
    latest = 0
    last_ts = 0
    if len(oldmessages) > 0:
        last_ts = oldmessages[-1]['ts']
    while has_more:
        convs_json = slackApi('conversations.history',{
            'channel': _id,
            'count': '1000',
            'latest': str(latest),
            'oldest': str(last_ts),
            })
        try:
            has_more = convs_json['has_more']
        except KeyError as e:
            print(f"Got KeyError while checking for has_more: {e}")
            print("Got this from slack:")
            pprint.pprint(convs_json)
            has_more = False
        for i in convs_json['messages']:
            oldmessages.append(i)
            latest = i['ts']
    oldmessages.sort(key = lambda msg: msg['ts'])
    return oldmessages

# loads the members of channel/group 'id',
def getChannelMembers(_id):
    convs_json = slackApi('conversations.members',{
            'channel': _id,
            'limit': '1000',
            })
    try:
        return convs_json['members']
    except KeyError:
        return []

# iterate over all channels/groups given as 'channels' dict,
# fetches their complete history and writes them to a json file,
# type must be 'channel' or 'group'
def fetchChannels(channels, _type, subdir):
    if not os.path.isdir(subdir):
        os.mkdir(subdir)
    for c in channels:
        name = ''
        if _type == 'im':
            name = channels[c]['user']
            if name != 'USLACKBOT':
                name = USERS[name]['name']
        else:
            name = channels[c]['name']
        verboseprint("  "+name)
        oldchannel = readJson(c, subdir)
        oldmessages = []
        if oldchannel is not None:
            oldmessages = oldchannel['messages']
        channels[c]['messages'] = getHistory(c, _type, oldmessages)
        channels[c]['members'] = getChannelMembers(c)
        writeJson(c, channels[c], subdir)

# loads the list of all files with all their attributes
def getFiles():
    page = 1
    pages = 2
    files = []
    while page < pages:
        files_json = slackApi('files.list',{
            'count': '1000',
            'page': str(page),
            })
        if 'error' in files_json and files_json['error'] in ['solr_failed']:
            print(f'getFiles(): Got error "{files_json["error"]}", retrying ...')
            files_json = slackApi('files.list',{
                'count': '1000',
                'page': str(page),
            })
        try:
            pages = int(files_json['paging']['pages'])
        except KeyError as e:
            pprint.pprint(files_json)
            raise e
        page += 1
        for i in files_json['files']:
            files.append(i)
    return files

# iterate over all files given as 'files' array,
# fetches their complete history and writes them to a json file,
def fetchFiles(files, oldfiles): # pylint: disable=too-many-branches
    oldfiledict = {}
    if oldfiles is not None:
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
        outfilename = 'files'+os.sep+f['id']+'.'+f['filetype']
        if os.path.isfile(outfilename) and f['id'] in oldfiledict:
            verboseprint("  "+f['name']+" (already downloaded)")
            continue
        if f['id'] in oldfiledict and f['timestamp'] == oldfiledict[f['id']]['timestamp']:
            infoprint("  "+f['name']+" (modified, redownloading)")
        else:
            infoprint("  "+f['name'])
        download_url = ''
        if 'url_download' in f:
            download_url = f['url_download']
        elif 'url_private_download' in f:
            download_url = f['url_private_download']
        elif 'permalink' in f:
            download_url = f['permalink']
        else:
            pprint.pprint(f)
            print('Error: Could not find suitable url to download this file')
            return
        req = requests.get(download_url, headers={'Authorization': f'Bearer {token}'}, timeout=30)
        if req.status_code != 200:
            print('Error fetching file '+f['id']+' from '+download_url)
            print(f'status_code: {req.status_code}')
        else:
            with io.open(outfilename, 'wb') as out:
                out.write(req.content)

def usage(exitcode):
    print("")
    print("Usage: archive-slack.py [options] <auth-token>")
    print("")
    print("Options:")
    print("    -h --help      : print this help")
    print("    -q --quiet     : no output except errors")
    print("    -v --verbose   : verbose output")
    print("    -p --no-public : skip download of public channels, private groups and files")
    print("    -P --private   : include direct messages and private files")
    print("")
    print("Use https://api.slack.com/#auth to generate your auth-token.")
    sys.exit(exitcode)

def verboseprint(text):
    if verbose:
        print(text)

def infoprint(text):
    if not quiet:
        print(text)

#
# main
#

# for all api calls, we need a https connection to slack.com
hcon = http.client.HTTPSConnection('slack.com')
opts, ARGS = getopt.gnu_getopt(sys.argv,
                               'hqvpP',
                               [
                                   'help',
                                   'quiet',
                                   'verbose',
                                   'no-public',
                                   'private',
                                   ])
# and a authentication token, given via cmdline arg,
# use https://api.slack.com/#auth to generate your own
if len(ARGS) != 2:
    usage(1)
token = ARGS[1]

quiet = False
verbose = False
nopublic = False
private = False

for o, v in opts:
    if o in ['--help', '-h']:
        usage(0)
    elif o in ['--quiet', '-q']:
        quiet = True
    elif o in ['--verbose', '-v']:
        verbose = True
    elif o in ['--no-public', '-p']:
        nopublic = True
    elif o in ['--private', '-P']:
        private = True
    else:
        usage(1)

# verbose overrides quiet
if verbose:
    quiet = False

if not nopublic or private:
    USERS = getUsers()
if not nopublic:
    writeJson('users', USERS)
    infoprint("Channels")
    CHANNELS = getChannels()
    writeJson("channels", CHANNELS)
    fetchChannels(CHANNELS, 'channels', 'channels')
    infoprint("Groups")
    GROUPS = getGroups()
    writeJson("groups", GROUPS)
    fetchChannels(GROUPS, 'groups', 'groups')
    infoprint("Files")
    FILES = getFiles()
    OLDFILES = readJson('files')
    fetchFiles(FILES, OLDFILES)
    writeJson('files', FILES)
if private:
    infoprint("DMs")
    fetchChannels(getDMs(), 'im', 'dms')
