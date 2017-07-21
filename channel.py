#!/usr/bin/python

import httplib, json, pprint, sys, os, getopt, time, datetime, re

users = {}
channels = {}

# reads a json input file 'name.json' returning deserialized data
def readJson(name):
    if os.path.isfile(name):
        f = open(name, 'r')
        data = json.loads(f.read())
        f.close()
        return data
    else:
        return None

def userid2name(user):
    if user == u'USLACKBOT':
        return 'Slack Bot'
    elif users.has_key(user):
        if users[user]['deleted']:
            return users[user]['name']+" (deleted)"
        else:
            return users[user]['real_name']
    else:
        if user != 'Ingress - Google+ Posts' and user != 'NIA Ops - Google+ Posts':
            print "Returning %s as not found" % user
        return user

def userid2username(user):
    if user == u'USLACKBOT':
        return 'slackbot'
    elif users.has_key(user):
        return users[user]['name']
    else:
        if user != 'Ingress - Google+ Posts' and user != 'NIA Ops - Google+ Posts':
            print "Returning %s as not found" % user
        return user

def channelid2name(channel):
    if channels.has_key(channel):
        return channels[channel]['name']
    else:
        return "unknown:"+channel

def ts2date(ts):
    return datetime.datetime.fromtimestamp(
        int(ts[:10])
        ).strftime("%F %R")

def ts2dateid(ts):
    return datetime.datetime.fromtimestamp(
        int(ts[:10])
        ).strftime("%F")

def matchReference(match):
    out = ""
    linktext = ""
    if match.group(5) == '|':
        linktext = match.group(6)
    if match.group(2) == '@':
        if linktext != "":
            out = linktext
        else:
            out = "@%s" % userid2username(match.group(3))
    elif match.group(2) == '#':
        if linktext != "":
            out = linktext
        else:
            out = "#%s" % channelid2name(match.group(3))
    else:
        out = "[[%s" % match.group(1)
        if linktext != "":
            out += "|%s" % linktext
        out += "]]"
    return out

def textToWiki(text):
    reffmt = re.compile('<((.)([^|>]*))((\|)([^>]*)|([^>]*))>')
    text = reffmt.sub(matchReference, text)
    text = text.replace("'", "&apos;")
    text = text.replace("\n", " <<BR>>\n")
    return text

def messageToWiki(m, edited = False):
    out = ""
    user = ""
    text = ""
    fmt_before = ""
    fmt_after = ""
    msgtype = "message"

    if not m.has_key('type') or m['type'] != 'message':
        print "Unknown message type:"
        pprint.pprint(m)
        return None, None

    if m.has_key('hidden') and m['hidden']:
        return None, None

    if m.has_key('subtype'):
        msgtype = m['subtype']
        try:
            if m['subtype'] == 'message_deleted':
                return None, None
            elif m['subtype'] == 'message_changed':
                return messageToWiki(m['message'], edited = True)

            elif m['subtype'] == 'channel_join' or \
                    m['subtype'] == 'channel_leave' or \
                    m['subtype'] == 'group_join' or \
                    m['subtype'] == 'group_leave':
                user = m['user']
                text = "joined #%s" % channel['name']
                fmt_before = fmt_after = "''"
            elif m['subtype'] == 'channel_topic' or \
                    m['subtype'] == 'channel_purpose' or \
                    m['subtype'] == 'group_topic' or \
                    m['subtype'] == 'group_purpose' or \
                    m['subtype'] == 'channel_archive' or \
                    m['subtype'] == 'channel_unarchive' or \
                    m['subtype'] == 'channel_name' or \
                    m['subtype'] == 'group_archive' or \
                    m['subtype'] == 'group_unarchive' or \
                    m['subtype'] == 'group_name':
                user = m['user']
                text = m['text']
                fmt_before = fmt_after = "''"

            elif m['subtype'] == 'bot_message':
                user = m['username']
                text = m['text']
                # pprint.pformat(m)
            elif m['subtype'] == 'me_message':
                user = m['user']
                text = m['user']+" "+m['text']
                fmt_before = fmt_after = "''"

            elif m['subtype'] == 'file_share':
                if m['text'] == 'A deleted file was shared':
                    return None, None
                user = m['user']
                text = m['file']['permalink']
                if m['file'].has_key('initial_comment'):
                    text += "\n    "+m['file']['initial_comment']['comment']
            elif m['subtype'] == 'file_comment':
                if m['text'] == 'A deleted file was commented on':
                    return None, None
                user = m['comment']['user']
                text += m['text']

            else:
                print "unknown subtype '"+m['subtype']+"':"
                pprint.pprint(m)

        except Exception, e:
            print e
            pprint.pprint(m)
            exit(1)
    else:
        user = m['user']
        text = m['text']

    if user == "":
        print "no user found for message:"
        pprint.pprint(m)

    out += "'''%s''' ~-%s-~<<BR>>\n" % (
        userid2name(user),
        ts2date(m['ts'])
        )
    out += fmt_before
    out += textToWiki(text)
    out += fmt_after
    if edited:
        out += " (edited)"
    out += "\n\n"
    dateid = ts2dateid(m['ts'])
    return dateid, out

def channelToWiki(channel):
    header = ""
    header += "= #%s =\n" % channel['name']
    if channel['purpose']['value'] != "":
        header += "=== %s ===\n" % channel['purpose']['value']
    if channel['topic']['value'] != "":
        header += "==== %s ====\n" % channel['topic']['value']
    header += "\n"
    if channel['is_archived']:
        header += " * archiviert\n"
    header += " * Mitglieder\n"
    members = map(userid2username, channel['members'])
    members.sort()
    for m in members:
        header += "  * %s\n" % m
    header += "\n"
    messages = {}
    count = 0
    for m in channel['messages']:
        dateid, msg = messageToWiki(m)
        if dateid != None:
            count += 1
            if not messages.has_key(dateid):
                messages[dateid] = []
            messages[dateid].append(msg)
    return count, header, messages



opts, args = getopt.gnu_getopt(sys.argv,
                               'hqv',
                               [
                                   'help',
                                   'quiet',
                                   'verbose',
                                   'users-file=',
                                   'channels-file=',
                                   ])
if len(args) != 2:
    usage(2)
channelfile = args[1]

quiet = False
verbose = False
usersfile = None
channelsfile = None

for o, v in opts:
    if o == '--help' or o == '-h':
        usage(0)
    elif o == '--quiet' or o == '-q':
        quiet = True
    elif o == '--verbose' or o == '-v':
        verbose = True
    elif o == '--users-file':
        usersfile = v
    elif o == '--channels-file':
        channelsfile = v
    else:
        usage(1)

if usersfile != None:
    json = readJson(usersfile)
    for u in json:
        users[json[u]['id']] = json[u]
        #print "%s\t%s" % (u, json[u]['name'])

if channelsfile != None:
    channels = readJson(channelsfile)

channel = readJson(args[1])

users = {}
if channel != None:
    for m in channel['messages']:
        if 'text' in m and 'ts' in m and 'user' in m:
            #print "%s %s" % (m['ts'], m['user'])
            users[m['user']] = m['ts']
    for u in users.keys():
        print "%s %s" % (users[u], u)

#    count, header, messages = channelToWiki(channel)
#    print header.encode('utf-8')
#    days = messages.keys()
#    days.sort()
#    for day in days:
#        for m in messages[day]:
#            print m.encode('utf-8')
else:
    print "Channel not found"
