#!/usr/bin/python3
# pylint: disable=missing-function-docstring,missing-module-docstring,invalid-name

import json
import pprint
import sys
import os
import io
import datetime
import re
import xmlrpc.client
# pylint: disable=deprecated-module
import getopt

users = {}
channels = {}
wikiusers = {}
VERBOSE = False
SPECIAL_USERS = [ 'Ingress - Google+ Posts', 'NIA Ops - Google+ Posts', 'IFTTT', 'bot' ]

def debug_print(s):
    if VERBOSE:
        print(s)

# reads a json input file 'name.json' returning deserialized data
def readJson(name):
    if os.path.isfile(name):
        with io.open(name, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())
        return data
    return None

def userid2name(user):
    if user == 'USLACKBOT':
        return 'Slack Bot'
    if user in users:
        if users[user]['deleted']:
            return users[user]['name']+" (deleted)"
        return users[user]['real_name']
    if user.startswith('bot_as:'):
        user = f'{user[7:]} (via Bot)'
    elif not user in SPECIAL_USERS:
        print("Returning {user} as not found name")
    return user

def userid2username(user):
    if user == 'USLACKBOT':
        return 'slackbot'
    if user in users:
        return users[user]['name']
    if not user in SPECIAL_USERS:
        print(f"Returning {user} as not found username")
    return user

def channelid2name(channel):
    if channel in channels:
        return channels[channel]['name']
    return "unknown:"+channel

def ts2date(ts):
    return datetime.datetime.fromtimestamp(
        int(ts[:10])
        ).strftime("%F %R")

def ts2dateid(ts):
    return datetime.datetime.fromtimestamp(
        int(ts[:10])
        ).strftime("%Y-%m")

def matchReference(refmatch):
    out = ""
    linktext = ""
    if refmatch.group(5) == '|':
        linktext = refmatch.group(6)
    if refmatch.group(2) == '@':
        if linktext != "":
            out = linktext
        else:
            out = f"@{userid2username(refmatch.group(3))}"
    elif refmatch.group(2) == '#':
        if linktext != "":
            out = linktext
        else:
            out = f"#{channelid2name(refmatch.group(3))}"
    else:
        out = f"[[{refmatch.group(1)}"
        if linktext != "":
            out += f"|{linktext}"
        out += "]]"
    return out

def textToWiki(text):
    reffmt = re.compile(r'<((.)([^|>]*))((\|)([^>]*)|([^>]*))>')
    text = reffmt.sub(matchReference, text)
    text = text.replace("'", "&apos;")
    text = text.replace("\r\n", "\n")
    text = text.replace("\n", " <<BR>>\n")
    return text

def messageToWiki(m, edited = False):
    # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
    out = ""
    user = ""
    text = ""
    fmt_before = ""
    fmt_after = ""

    if 'type' not in m or m['type'] != 'message':
        print("Unknown message type:")
        pprint.pprint(m)
        return None, None

    if 'hidden' in m and m['hidden']:
        return None, None

    if 'subtype' in m:
        try:
            if m['subtype'] in [
                    'message_deleted',
                    'pinned_item',
                    'reply_broadcast',
                    'thread_broadcast'
            ]:
                return None, None
            if m['subtype'] == 'message_changed':
                return messageToWiki(m['message'], edited = True)

            if m['subtype'] == 'channel_join' or \
                    m['subtype'] == 'channel_leave' or \
                    m['subtype'] == 'group_join' or \
                    m['subtype'] == 'group_leave':
                user = m['user']
                text = f"joined #{CHANNEL['name']}"
                fmt_before = fmt_after = "''"
            elif m['subtype'] in [
                    'channel_topic',
                    'channel_purpose',
                    'group_topic',
                    'group_purpose',
                    'channel_archive',
                    'channel_unarchive',
                    'channel_name',
                    'group_archive',
                    'group_unarchive',
                    'group_name',
                    ]:
                user = m['user']
                text = m['text']
                fmt_before = fmt_after = "''"

            elif m['subtype'] == 'bot_message':
                user = m['username']
                if user == 'IFTTT':
                    if 'text' in m['attachments'][0]:
                        text = m['attachments'][0]['text']
                    elif 'pretext' in m['attachments'][0]:
                        text = m['attachments'][0]['pretext']
                    else:
                        print("Could not handle new type bot message:")
                        pprint.pprint(m)
                        return None, None
                else:
                    text = m['text']
                if not user in  SPECIAL_USERS:
                    user = f'bot_as:{user}'

            elif m['subtype'] == 'slackbot_response':
                user = m['user']
                text = m['text']

            elif m['subtype'] in [ 'me_message', 'reminder_add', 'bot_remove', 'bot_add' ]:
                user = m['user']
                text = '<@'+m['user']+"> "+m['text']
                fmt_before = fmt_after = "''"

            elif m['subtype'] == 'file_share':
                if m['text'] == 'A deleted file was shared' or not m['upload']:
                    return None, None
                user = m['user']
                text = m['file']['permalink']
                if 'initial_comment' in m['file']:
                    text += "\n    "+m['file']['initial_comment']['comment']
            elif m['subtype'] == 'file_comment':
                if m['text'] == 'A deleted file was commented on' or m['comment'] is None:
                    return None, None
                user = m['comment']['user']
                text += m['text']
            elif m['subtype'] == 'file_mention':
                if m['text'] == 'A deleted file was mentioned on':
                    return None, None
                user = m['user']
                text += m['text']

            else:
                print("unknown subtype '"+m['subtype']+"':")
                pprint.pprint(m)

        except Exception as e:
            pprint.pprint(m)
            raise e
    else:
        user = m['user']
        text = m['text']

    if user == 'Patrick C.':
        pprint.pprint(m)

    if user == "":
        print("no user found for message:")
        pprint.pprint(m)

    out += f"'''{userid2name(user)}''' ~-{ts2date(m['ts'])}-~<<BR>>\n"
    out += fmt_before
    out += textToWiki(text)
    out += fmt_after
    if edited:
        out += " (edited)"
    out += "\n\n"
    dateid = ts2dateid(m['ts'])
    return dateid, out

def slackuser2wikiuser(u):
    if u in wikiusers:
        return wikiusers[u]
    return f"UnknownWikiUser_{u}"

def channelToWiki(channel):
    header = ""
    members = list(map(userid2username, channel['members']))
    members.sort()
    is_group = False
    if 'is_group' in channel and channel['is_group']:
        is_group = True
        header += "#acl slackbot:read,write,delete,revert,admin "
        header += ",".join(map(slackuser2wikiuser, members))
        header += ":read All:\n\n"
    if is_group:
        channelmarker = ""
    else:
        channelmarker = "#"
    header += f"= {channelmarker}{channel['name']} =\n"
    if channel['purpose']['value'] != "":
        header += "=== %s ===\n" % channel['purpose']['value'].replace('\r', ' ').replace('\n', ' ')
    if channel['topic']['value'] != "":
        header += "==== %s ====\n" % channel['topic']['value'].replace('\r', ' ').replace('\n', ' ')
    header += "\n"
    if channel['is_archived']:
        header += " * archiviert\n"
    header += " * Mitglieder\n"
    for m in members:
        header += f"  * {m}\n"
    header += "\n"
    messages = {}
    for m in channel['messages']:
        dateid, msg = messageToWiki(m)
        if dateid:
            if dateid not in messages:
                messages[dateid] = []
            messages[dateid].append(msg)
    return header, messages

def writeWikipage(content, wikiurl, pagename, username, password):
    # pylint: disable=too-many-locals,too-many-branches
    try:
        homewiki = xmlrpc.client.ServerProxy(wikiurl + "?action=xmlrpc2", allow_none=True)
        auth_token = homewiki.getAuthToken(username, password)
        mc = xmlrpc.client.MultiCall(homewiki)
        mc.applyAuthToken(auth_token)
        success = False
        oldcontent = ""
        try:
            mc.getPage(pagename)
            result = mc()
            success, oldcontent = tuple(result)
        except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as ex:
            if str(ex) == "<Fault 1: 'No such page was found.'>":
                success = False
            else:
                print(f"Unexpected error while getpage({pagename}), raising again:")
                str(ex)
                raise ex
        if not success:
            oldcontent = ""
        else:
            oldcontent = oldcontent+"\n"
        if oldcontent != content:
            debug_print("Writing "+wikiurl+"/"+pagename)
            if VERBOSE:
                import difflib # pylint: disable=import-outside-toplevel
                for l in difflib.unified_diff(
                        oldcontent.split('\n'),
                        content.split('\n'),
                        fromfile='oldcontent',
                        tofile='newcontent'
                ):
                    debug_print(l.rstrip())
            try:
                mc.putPage(pagename, content)
                results = []
                multiresult = mc()
                for i in multiresult:
                    results.append(i)
                if results[0] != 'SUCCESS':
                    print('Authentication failed!')
                if not results[1]:
                    print('Failed to write page!')
            except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as ex:
                if 'No such page was found' not in str(ex):
                    print(f"Unexpected error while putpage({pagename}), raising again:")
                    print(str(ex))
#        else:
#            debug_print("Skipping "+wikiurl+"/"+pagename+" with unchanged content")
    except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as ex:
        print(f"pagename={pagename}")
        print('XMLRPC: ' + str(ex))
        raise ex
    return True

def getWikipage(wikiurl, pagename, username, password):
    content = ""
    try:
        homewiki = xmlrpc.client.ServerProxy(wikiurl + "?action=xmlrpc2", allow_none=True)
        auth_token = homewiki.getAuthToken(username, password)
        mc = xmlrpc.client.MultiCall(homewiki)
        mc.applyAuthToken(auth_token)
        success = False
        try:
            mc.getPage(pagename)
            result = mc()
            success, content = tuple(result)
        except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as ex:
            if str(ex) == "<Fault 1: 'No such page was found.'>":
                success = False
            else:
                print(f"Unexpected error while getpage({pagename}), raising again:")
                str(ex)
                raise ex
        if not success:
            content = ""
        else:
            content = content+"\n"
    except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as ex:
        print(f"pagename={pagename}")
        print('XMLRPC: ' + str(ex))
        raise ex
    return content

def fileToWiki(f):
    content = ""
    #channels = f['channels']
    #groups = f['groups']
    content += "= " + f['title'] + " =\n"
    content += "\n"
    return content

def usage(exitcode):
    print("usage")
    sys.exit(exitcode)

opts, args = getopt.gnu_getopt(sys.argv,
                               'hqv',
                               [
                                   'help',
                                   'quiet',
                                   'verbose',
                                   'users-file=',
                                   'channels-file=',
                                   'groups-file=',
                                   'files-file=',
                                   'wiki-user=',
                                   'wiki-pass=',
                                   'wiki-members-page=',
                                   ])
if len(args) < 3:
    usage(1)
WIKIRUL = args[1]
renderchannels = args[2:]

quiet = False
usersfile = None
channelsfile = None
groupsfile = None
filesfile = None
wikiuser = None
wikipass = None
wikimemberspage = None

for o, v in opts:
    if o in ['--help', '-h']:
        usage(0)
    elif o in ['--quiet', '-q']:
        quiet = True
    elif o in ['--verbose', '-v']:
        VERBOSE = True
    elif o == '--users-file':
        usersfile = v
    elif o == '--channels-file':
        channelsfile = v
    elif o == '--groups-file':
        groupsfile = v
    elif o == '--files-file':
        filesfile = v
    elif o == '--wiki-user':
        wikiuser = v
    elif o == '--wiki-pass':
        wikipass = v
    elif o == '--wiki-members-page':
        wikimemberspage = v
    else:
        usage(1)

if usersfile:
    userjson = readJson(usersfile)
    for slackuser in userjson:
        users[userjson[slackuser]['id']] = userjson[slackuser]

if channelsfile:
    channels = readJson(channelsfile)
if groupsfile:
    groups = readJson(groupsfile)
    for g in list(groups.keys()):
        channels[g] = groups[g]

if wikimemberspage:
    wikiuserpage = getWikipage(WIKIRUL, wikimemberspage, wikiuser, wikipass)
    itemfmt = re.compile(r'\s+\*\s+(\S+)')
    for line in wikiuserpage.split("\n"):
        match = itemfmt.match(line)
        if match:
            member = match.group(1)
            lcuser = member.lower()
            wikiusers[lcuser] = member

if filesfile:
    print("Files not supported yet")
    sys.exit(1)
    # pylint: disable=unreachable
    files = readJson(filesfile)
    for slackfile in files:
        print(fileToWiki(slackfile))

for c in renderchannels:
    CHANNEL = readJson(c)

    if CHANNEL:
        HEADER, MESSAGES = channelToWiki(CHANNEL)
        dateids = list(MESSAGES.keys())
        dateids.sort()
        for did in dateids:
            page = HEADER
            for message in MESSAGES[did]:
                page += message
            writeWikipage(page, WIKIRUL, "Slack/"+CHANNEL['name']+"/"+did, wikiuser, wikipass)
    else:
        print("Channel not found")
