from jira.client import JIRA
from jy.ioutil import load, dump
import copy
import os
import sys


SHORTENED = [('assignee', 'name'), ('project', 'key'), ('reporter', 'name'), ('issuetype', 'name'),
             ('at', 'name'),
             ('zone', 'value'), ('ptype', 'value')]
SHORTENED_LISTS = [('components', 'name'),
                   ('fixVersions', 'name'),
                   ('customer', '')]


def map_custom_fields(item, fields):
    for f, k in SHORTENED:
        if isinstance(item.get(f), basestring):
            item[f] = {k: item[f]}

    for f, k in SHORTENED_LISTS:
        l = item.get(f, [])
        if not isinstance(l, list):
            item[f] = l = [l]
        for i, el in enumerate(l):
            if isinstance(el, basestring) and k:
                item[f][i] = {k: el}
    for k in fields:
        if k in item:
            item[fields[k]] = item.pop(k)

    f = 'issueLinks'
    for i, link in enumerate(item.get(f, [])):
        if isinstance(link, basestring):
            item[f][i] = dict(key=link, type="relates to")


def create_issue(jira, manifest, item, **kwargs):
    kw = copy.copy(manifest)
    kw.update(item)
    kw.pop("subtasks", None)
    kw.update(kwargs)
    links = kw.pop("issueLinks", [])
    try:
        issue = jira.create_issue(**kw)
    except:
        print kw
        raise
    return issue, links


def map_users(item, users):
    for k in ['assignee', 'reporter']:
        if item.get(k) in users:
            item[k] = users[item.get(k)]

def do_stuff(jira, manifest, items):
    custom_fields = manifest.pop("customFields", {})
    users = manifest.pop("users", {})

    def transform(item):
        map_users(item, users)
        map_custom_fields(item, custom_fields)

    original_manifest = copy.deepcopy(manifest)
    transform(manifest)
    for item in items:
        if '-ignore' in item:
            continue
        if '+block' in item:
            if 'summary' in item:
                v = [("*" * 80), item['summary'], ("*" * 80)]
            else:
                v = [("*" * 80), ("*" * 80)]
            item.apply('+block', v)
        if '+comment' in item:
            comment = item.pop('+comment')
            jira.add_comment(item['key'], comment)
            item.rm('+comment')
            print "Added to", item['key'], comment
        if 'manifest' in item:
            manifest = copy.deepcopy(original_manifest)
            manifest.update(item['manifest'])
            transform(manifest)
            continue
        if 'search' in item:
            continue
        if 'key' not in item:
            transform(item)
            issue, links = create_issue(jira, manifest, item)
            item.apply('key', str(issue.key))
            for link in links:
                if isinstance(link, basestring):
                    link = dict(type="relates to", key=link)
                jira.create_issue_link(link.get('type', 'relates to'), issue.key, link['key'])
            print "Created", issue.key
        for i, task in enumerate(item.get("subtasks") or []):
            if 'key' not in task:
                if 'assignee' not in task and 'assignee' in item:
                    task['assignee'] = item['assignee']
                transform(task)
                st, _ = create_issue(jira, dict(project=manifest['project'],
                                                assignee=manifest['assignee'],
                                                reporter=manifest['reporter']),
                                     task, parent=dict(key=item['key']), issuetype=dict(id=5))
                print "Created", st.key
                item['subtasks'][i].apply('key', str(st.key))
    found = True
    while found:
        found = False
        for i_, item in enumerate(items[1:]):
            if 'search' not in item:
                continue
            if item.get('complete'):
                continue
            found = True
            item.apply('complete', True)
            for j, issue in enumerate(jira.search_issues(item['search'])):
                data = dict(key=str(issue.key),
                            summary=str(issue.fields.summary),
                            assignee=str(issue.fields.assignee.name),
                            status=str(issue.fields.status.name))
                            #components=map(lambda x: str(x.name), issue.fields.components))
                item.parent.insert(i_ + 2 + j, data)
            break


def connect(server=None, username=None, password=None):
    def _value(name, value):
        return value or os.environ['JY_%s' % name.upper()]

    return JIRA(options={'server': _value('server', server)},
                      basic_auth=(_value('username', username),
                                  _value('password', password)))


def main():
    jira = connect()
    args = sys.argv[1:]
    if len(args) == 1:
        infile = outfile = args[0]
    else:
        infile, outfile = args[0], args[1]
    items = load(open(infile))

    manifest = {}
    defaults = os.path.expanduser("~/.jy")
    if os.path.exists(defaults):
        manifest.update(load(open(defaults)))

    manifest.update(items[0])
    
    try:
        do_stuff(jira, manifest, items[1:])
    finally:
        with open(outfile, "w") as f:
            dump(items, f, default_flow_style=False)


if __name__ == '__main__':
    main()
