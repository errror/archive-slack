#!/usr/bin/python
# apt-get install python-anyjson


import anyjson, pprint, sys, os, getopt, json, time



# reads a json input file 'name.json' returning deserialized data
def readJson(name, subdir="."):
    if os.path.isfile(subdir + os.sep + name + '.json'):
        f = open(subdir + os.sep + name + '.json', 'r')
        data = anyjson.deserialize(f.read())
        f.close()
        return data
    else:
        return None


# writes a json output file 'name.json' containing json serialization of 'data'
def writeHTML(name, data, subdir="html"):
    f = open(subdir + os.sep + name + '.html', 'w')
    f.write(data)
    f.close()


def itemName(item, users):
    if 'name' in item:
        return item['name']
    else:
        return dmUserName(item, users)


# format a single message according to the rules
def formatMessage(message, users):
    res = '<div class="message"><div class="timestamp">' + \
          time.strftime('%H:%M:%S', time.localtime(float(message['ts']))) + \
          '</div><div class="message_content">'
    userColor=''
    if 'username' in message:
        username = message['username']
    elif 'user' in message:
        uid = message['user']
        username= user_name(uid, users)
        if uid in users and 'color' in users[uid]:
            userColor='style="color: #'+users[uid]['color']+'"'
    else:
        username = '????'
    res += '<div class="message_user" '+userColor+'>'+username + '</div> '
    res += message['text']
    res += '</div></div>'
    return res


# returns basic header for all generated html files
def htmlHeader(title):
    res = '''<!doctype html>
<html>
    <head>
		<meta charset="UTF-8">
        <title>''' + title + '''</title>
        <link rel="stylesheet" type="text/css" href="style.css"/>
    </head>
    <body>
	'''
    return res

# default footer.
def htmlFooter():
    return '''</body></html>'''

# formats a channel contents into a single html returned as string.
def prepareChannelContent(channel, users, item_type='channel'):
    item_name=itemName(channel, users)
    content = htmlHeader(item_name)
    content += '<h2>' + ('#' if item_type=='channel'else '') + item_name + '</h2>\n'
    messages = channel['messages']
    current_day = None
    for message in messages:
        mg_day = time.strftime('%Y%j', time.localtime(float(message['ts'])))
        if (current_day != mg_day):
            current_day = mg_day
            content += '<div class="date_separator">' + time.strftime('%Y-%m-%d',
                                                                      time.localtime(float(message['ts']))) + '</div>\n'
        content += formatMessage(message, users)
        content += '\n'
    content += htmlFooter()
    return content


def prepareGroupList(channels):
    html='<ul class="channel_list">\n'
    if channels:
        channel_ids = sorted(channels.keys(), key=lambda key: channels[key]['name'])
        for channel_id in channel_ids:
            channel = channels[channel_id]
            html += '<li><a href="' + channel_id + '.html">' + channel['name'] + '</a></li>\n'
        html += '</ul>\n'
    return html


#Human readable user name (include Slackbot and unknown cases)
def user_name(uid, users):
    if uid in users:
        return users[uid]['name']
    elif uid=='USLACKBOT':
        return "Slackbot"
    else:
        return "Unknown ("+uid+")"

def dmUserName(dm, users):
    uid=dm['user']
    return user_name(uid, users)

#prepare index.html with links to
def prepareTOC(channels, groups, dms, users):
    html=htmlHeader('Slack dump')
    if channels:
        html += '<h2>Channels</h2>\n'
        html += prepareGroupList(channels)
    if groups:
        html += '<h2>Groups</h2>\n'
        html += prepareGroupList(groups)
    if dms:
        html += '<h2>DMs</h2>\n'
        html += '<ul class="channel_list">\n'
        dms_ids=sorted(dms.keys(), key=lambda key: dmUserName(dms[key], users).lower())
        for dm_id in dms_ids:
            dm = dms[dm_id]
            username = dmUserName(dm, users)
            html += '<li><a href="'+dm_id+'.html">'+username+'</a></li>\n'
        html += '</ul>\n'

    html += htmlFooter()
    return html


def verboseprint(text):
    if verbose:
        print(text)
        #text.encode('ascii', 'ignore')


def infoprint(text):
    if not quiet:
        print(text)
        #text.encode('ascii', 'ignore')



def exportClass(items, users, type, dir):
    for item in items:
        verboseprint('Exporting '+type+' '+itemName(items[item], users))
        item_content = readJson(item, dir)
        html = prepareChannelContent(item_content, users, type)
        writeHTML(item, html)
    return

def usage(exitcode):
    print("")
    print("Usage: json2html.py [options] <auth-token>")
    print("")
    print("Run this program in the root directory where previously archive-slack has been run.")
    print("Options:")
    print("    -h --help      : print(this help")
    print("    -q --quiet     : no output except errors")
    print("    -v --verbose   : verbose output")
    print("")
    exit(exitcode)

opts, args = getopt.gnu_getopt(sys.argv, 'hqv', ['help', 'quiet', 'verbose'])
# and a authentication token, given via cmdline arg, use https://api.slack.com/#auth to generate your own
if len(args) != 1:
    usage(1)

quiet = False
verbose = False

for o, v in opts:
    if o == '--help' or o == '-h':
        usage(0)
    elif o == '--quiet' or o == '-q':
        quiet = True
    elif o == '--verbose' or o == '-v':
        verbose = True
    else:
        usage(1)

# verbose overrides quiet
if verbose:
    quiet = False

#read channels
if not os.path.isdir("html"):
    infoprint("Creating 'html' directory")
    os.mkdir("html")
channels = readJson("channels")
groups = readJson("groups")
dms = readJson("dms")
users = readJson("users")
infoprint('Preparing index.html')
writeHTML("index", prepareTOC(channels, groups, dms, users))
infoprint("\n\nPreparing CHANNELS:")
exportClass(channels, users, 'channel', 'channels')
if groups:
    infoprint("\n\nPreparing GROUPS:")
    exportClass(groups, users, 'group', 'groups')
if dms:
    infoprint("\n\nPreparing DMs:")
    exportClass(dms, users, 'dm', 'dms')

# for channel in channels:
#     channelContent = readJson(channel, "channels")
#     verboseprint("Formatting channel: " + channelContent['name']);
#     html = prepareChannelContent(channelContent, users)
#     writeHTML(channel, html)
infoprint("Export complete.")
