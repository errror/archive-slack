#!/usr/bin/python

# apt-get install python-anyjson
import httplib, anyjson, pprint, sys, os, getopt, time, datetime, re, xmlrpclib

users = {}
channels = {}
wikiusers = {}
verbose = False

def debug_print(s):
    if verbose:
        print s

# reads a json input file 'name.json' returning deserialized data
def readJson(name):
    if os.path.isfile(name):
        f = open(name, 'r')
        data = anyjson.deserialize(f.read())
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
        if user.startswith('bot_as:'):
            user = '%s (via Bot)' % user[7:]
        elif not user in [ 'Ingress - Google+ Posts', 'NIA Ops - Google+ Posts', 'IFTTT', 'bot' ]:
            print "Returning %s as not found name" % user
        return user

def userid2username(user):
    if user == u'USLACKBOT':
        return 'slackbot'
    elif users.has_key(user):
        return users[user]['name']
    else:
        if not user in [ 'Ingress - Google+ Posts', 'NIA Ops - Google+ Posts', 'IFTTT', 'bot' ]:
            print "Returning %s as not found username" % user
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
        ).strftime("%Y-%m")

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
    text = text.replace("\r\n", "\n")
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
            elif m['subtype'] == 'pinned_item':
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
                if user == 'IFTTT':
                    if m['attachments'][0].has_key('text'):
                        text = m['attachments'][0]['text']
                    elif m['attachments'][0].has_key('pretext'):
                        text = m['attachments'][0]['pretext']
                    else:
                        print "Could not handle new type bot message:"
                        pprint.pprint(m)
                        return None, None
                else:
                    text = m['text']
                if not user in  [ 'Ingress - Google+ Posts', 'NIA Ops - Google+ Posts', 'IFTTT', 'bot' ]:
                    user = 'bot_as:%s' % user

            elif m['subtype'] == 'slackbot_response':
                user = m['user']
                text = m['text']

            elif m['subtype'] in [ 'me_message', 'reminder_add', 'bot_remove', 'bot_add' ]:
                user = m['user']
                text = '<@'+m['user']+"> "+m['text']
                fmt_before = fmt_after = "''"

            elif m['subtype'] == 'file_share':
                if m['text'] == 'A deleted file was shared' or m['upload'] == False:
                    return None, None
                user = m['user']
                text = m['file']['permalink']
                if m['file'].has_key('initial_comment'):
                    text += "\n    "+m['file']['initial_comment']['comment']
            elif m['subtype'] == 'file_comment':
                if m['text'] == 'A deleted file was commented on' or m['comment'] == None:
                    return None, None
                user = m['comment']['user']
                text += m['text']
            elif m['subtype'] == 'file_mention':
                if m['text'] == 'A deleted file was mentioned on':
                    return None, None
                user = m['user']
                text += m['text']

            else:
                print "unknown subtype '"+m['subtype']+"':"
                pprint.pprint(m)

        except Exception, e:
            pprint.pprint(m)
            raise e
    else:
        user = m['user']
        text = m['text']

    if user == 'Patrick C.':
        pprint.pprint(m)

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

def slackuser2wikiuser(u):
    if wikiusers.has_key(u):
        return wikiusers[u]
    else:
        return "UnknownWikiUser_%s" % u

def channelToWiki(channel):
    header = ""
    members = map(userid2username, channel['members'])
    members.sort()
    is_group = False
    if channel.has_key('is_group') and channel['is_group']:
        is_group = True
        header += "#acl slackbot:read,write,delete,revert,admin "
        header += ",".join(map(slackuser2wikiuser, members))
        header += ":read All:\n\n"
    if is_group:
        channelmarker = ""
    else:
        channelmarker = "#"
    header += "= %s%s =\n" % (channelmarker, channel['name'])
    if channel['purpose']['value'] != "":
        header += "=== %s ===\n" % channel['purpose']['value']
    if channel['topic']['value'] != "":
        header += "==== %s ====\n" % channel['topic']['value']
    header += "\n"
    if channel['is_archived']:
        header += " * archiviert\n"
    header += " * Mitglieder\n"
    for m in members:
        header += "  * %s\n" % m
    header += "\n"
    messages = {}
    for m in channel['messages']:
        dateid, msg = messageToWiki(m)
        if dateid != None:
            if not messages.has_key(dateid):
                messages[dateid] = []
            messages[dateid].append(msg)
    return header, messages

def writeWikipage(content, wikiurl, pagename, username, password):
    try:
        homewiki = xmlrpclib.ServerProxy(wikiurl + "?action=xmlrpc2", allow_none=True)
        auth_token = homewiki.getAuthToken(username, password)
        mc = xmlrpclib.MultiCall(homewiki)
        mc.applyAuthToken(auth_token)
        success = False
        oldcontent = ""
        try:
            mc.getPage(pagename)
            result = mc()
            success, oldcontent = tuple(result)
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError), ex:
            if str(ex) == "<Fault 1: 'No such page was found.'>":
                success = False
            else:
                print "Unexpected error while getpage(%s), raising again:" % pagename
                str(ex)
                raise ex
        if not success:
            oldcontent = ""
        else:
            oldcontent = oldcontent+"\n"
        if oldcontent != content:
            debug_print("Writing "+wikiurl+"/"+pagename)
            try:
                mc.putPage(pagename, content)
                results = []
                multiresult = mc()
                for i in multiresult:
                    results.append(i)
                if results[0] != 'SUCCESS':
                    print 'Authentication failed!'
                if not results[1]:
                    print 'Failed to write page!'
            except (xmlrpclib.Fault, xmlrpclib.ProtocolError), ex:
                if not 'No such page was found' in str(ex):
                    print "Unexpected error while putpage(%s), raising again:" % pagename
                    print str(ex)
#        else:
#            debug_print("Skipping "+wikiurl+"/"+pagename+" with unchanged content")
    except (xmlrpclib.Fault, xmlrpclib.ProtocolError), ex:
        print "pagename=%s" % pagename
        print 'XMLRPC: ' + str(ex)
        raise ex
    return True

def getWikipage(wikiurl, pagename, username, password):
    content = ""
    try:
        homewiki = xmlrpclib.ServerProxy(wikiurl + "?action=xmlrpc2", allow_none=True)
        auth_token = homewiki.getAuthToken(username, password)
        mc = xmlrpclib.MultiCall(homewiki)
        mc.applyAuthToken(auth_token)
        success = False
        try:
            mc.getPage(pagename)
            result = mc()
            success, content = tuple(result)
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError), ex:
            if str(ex) == "<Fault 1: 'No such page was found.'>":
                success = False
            else:
                print "Unexpected error while getpage(%s), raising again:" % pagename
                str(ex)
                raise ex
        if not success:
            content = ""
        else:
            content = content+"\n"
    except (xmlrpclib.Fault, xmlrpclib.ProtocolError), ex:
        print "pagename=%s" % pagename
        print 'XMLRPC: ' + str(ex)
        raise ex
    return content

def fileToWiki(f):
    content = ""
    channels = f['channels']
    groups = f['groups']
    content += "= " + f['title'] + " =\n"
    content += "\n"
    return content

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
    usage(2)
wikiurl = args[1]
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

if usersfile != None:
    json = readJson(usersfile)
    for u in json:
        users[json[u]['id']] = json[u]

if channelsfile != None:
    channels = readJson(channelsfile)
if groupsfile != None:
    groups = readJson(groupsfile)
    for g in groups.keys():
        channels[g] = groups[g]

if wikimemberspage:
    wikiuserpage = getWikipage(wikiurl, wikimemberspage, wikiuser, wikipass)
    itemfmt = re.compile('\s+\*\s+(\S+)')
    for line in wikiuserpage.split("\n"):
        match = itemfmt.match(line)
        if match != None:
            user = match.group(1)
            lcuser = user.lower()
            wikiusers[lcuser] = user

if filesfile != None:
    print "Files not supported yet"
    sys.exit(1)
    files = readJson(filesfile)
    for f in files:
        print fileToWiki(f)

for c in renderchannels:
    channel = readJson(c)

    if channel != None:
        header, messages = channelToWiki(channel)
        dateids = messages.keys()
        dateids.sort()
        for did in dateids:
            page = header
            for m in messages[did]:
                page += m
            writeWikipage(page, wikiurl, "Slack/"+channel['name']+"/"+did, wikiuser, wikipass)
    else:
        print "Channel not found"
