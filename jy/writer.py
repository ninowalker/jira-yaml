from jira.client import JIRA
import copy
import os
import shutil
import sys
import yaml

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


def do_stuff(jira, items, original):
    manifest = items.pop(0)
    custom_fields = manifest.pop("customFields", {})

    def transform(item):
        map_custom_fields(item, custom_fields)

    original_manifest = copy.deepcopy(manifest)
    transform(manifest)
    for item, orig in zip(items, original[1:]):
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
            item['key'] = orig['key'] = str(issue.key)
            for link in links:
                jira.create_issue_link(link['type'], issue.key, link['key'])
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
                orig['subtasks'][i]['key'] = str(st.key)
        for i, (collaborator, tasks) in enumerate((item.get("collaborators") or {}).iteritems()):
            for j, task in enumerate(tasks):
                if 'key' not in task:
                    transform(task)
                    st, _ = create_issue(jira,
                                         dict(project=manifest['project'],
                                              assignee=dict(name=collaborator),
                                              reporter=manifest['reporter']),
                                              task, parent=dict(key=item['key']), issuetype=dict(id=5))
                    print "Created", st.key
                    orig['collaborators'][collaborator][j]['key'] = str(st.key)
    found = True
    while found:
        found = False
        for i_, (item, orig) in enumerate(zip(items, original[1:])):
            if 'search' not in item:
                continue
            if 'complete' in item:
                continue
            found = True
            item['complete'] = orig['complete'] = True
            for j, issue in enumerate(jira.search_issues(item['search'])):
                data = dict(key=str(issue.key),
                            summary=str(issue.fields.summary),
                            assignee=str(issue.fields.assignee.name),
                            status=str(issue.fields.status.name))
                            #components=map(lambda x: str(x.name), issue.fields.components))
                original.insert(i_ + 2 + j, data)
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
    items = yaml.load(open(infile))
    orig = copy.deepcopy(items)
    try:
        do_stuff(jira, items, orig)
    finally:
        with open(outfile, "w") as f:
            yaml.dump(orig, f, default_flow_style=False)


if __name__ == '__main__':
    main()
