from jira.client import GreenHopper
from jy.ioutil import load, dump
from jy.transformers import ApplyTransformers, NewManifest, Transformer
from optparse import OptionParser
import copy
import functools
import os
import sys
from docopt import docopt


class Context(object):
    def __init__(self, jira):
        self.jira = jira
        self.manifests = []
        self.user_fields = ['assignee', 'reporter']
        self.aliases = {}
        self.user_aliases = {}
        self.objectified = {}

    def create_issue_from_item(self, item, **kwargs):
        params = self.compute_defaults()
        params.update(item)
        params.update(kwargs)
        self._squash_prefixed(params)
        params = self._normalize(params)
        try:
            issue = self.jira.create_issue(**params)
        except Exception, e:
            print >> sys.stderr, params
            print >> sys.stderr, e
            sys.exit(1)
        return issue

    def _squash_prefixed(self, params):
        """Ensure handle issuetype/value"""
        prefix = "%s/" % self._normalize(params)["issuetype"]['name']
        for key in params.keys():
            if key.startswith(prefix):
                pkey = key[len(prefix):]
                pval = params.pop(key)
                if pkey not in params:
                    params[pkey] = pval
            elif "/" in key:
                params.pop(key)

    def compute_defaults(self):
        params = {}
        for m in self.manifests:
            params.update(m)
        return params

    def create_subtask_from_item(self, task, parent):
        base_manifest = self.compute_defaults()
        params = dict(project=base_manifest['project'],
                      assignee=base_manifest['assignee'],
                      reporter=base_manifest['reporter'],
                      issuetype=dict(id=5),
                      parent=dict(key=parent['key']))

        if 'assignee' not in task and 'assignee' in parent:
            task['assignee'] = parent['assignee']
        params.update(task)
        kw = None
        try:
            kw = self._normalize(params)
            return self.jira.create_issue(**kw)
        except:
            print kw
            raise

    def update_objectified(self, k, v):
        if isinstance(v, basestring):
            self.objectified[k] = functools.partial(self._dictify, k, v)
        elif isinstance(v, list):
            self.objectified[k] = functools.partial(self._listify, k, v[0])

    def _dictify(self, k, dkey, item):
        if isinstance(item.get(k), basestring):
            item[k] = {dkey: item[k]}

    def _listify(self, k, dkey, item):
        l = item.get(k, [])
        if not isinstance(l, list):
            item[k] = l = [l]
        for i, el in enumerate(l):
            if isinstance(el, basestring) and k:
                item[k][i] = {dkey: el}

    def _normalize(self, item):
        item = copy.copy(item)
        for k in self.user_fields:
            user = item.get(k)
            if isinstance(user, basestring) and user in self.user_aliases:
                item[k] = self.user_aliases[user]

        # transform anything needing transformed
        for trans in self.objectified.values():
            trans(item)
        # map over aliased fields
        for k, v in self.aliases.items():
            if k in item:
                item[v] = item.pop(k)
        # pop out exceptional tags
        for trans in Transformer:
            for k in trans.ignored:
                item.pop(k, None)
        return item


def connect(conf):
    conf = conf or {}
    connection = conf.get('connection', {})
    def _value(name):
        return connection.get(name) or os.environ['JY_%s' % name.upper()]

    return GreenHopper(options={'server': _value('server')},
                       basic_auth=(_value('username'),
                                   _value('password')))


def mock_connect(conf):
    from mock import Mock
    jira = Mock(spec=GreenHopper)
    jira.search_issues.return_value = [Mock(), Mock()]
    
    def create_issue(**kwargs):
        m = Mock()
        m.key = kwargs
        return m
    jira.create_issue.side_effect = create_issue
    return jira


def main():
    """JIRA-Yaml Writer.

Usage:
  jywriter [options] <input>
  jywriter [options] <input> <output>
  
Options:
  -h --help     Show this screen.
  -t --test     Use a mock instead of connecting to JIRA.
    """
    arguments = docopt(main.__doc__)

    if arguments.get('--test'):
        _connect = mock_connect
        arguments['<output>'] = "/dev/stdout"
    else:
        _connect = connect

    if not arguments.get("<output>"):
        arguments['<output>'] = arguments['<input>']

    conf = None
    defaults = os.path.expanduser("~/.jy")
    if os.path.exists(defaults):
        conf = load(open(defaults))

    jira = connect(conf)
    items = load(open(arguments["<input>"]))
    context = Context(jira)

    if conf:
        NewManifest(context)(conf)
    try:
        ApplyTransformers(context)(items)
    finally:
        with open(arguments['<output>'], "w") as f:
            dump(items, f, default_flow_style=False)


if __name__ == '__main__':
    main()
