from jira.client import GreenHopper
from jy.ioutil import load, dump
from jy.transformers import ApplyTransformers, NewManifest, Transformer
from optparse import OptionParser
import copy
import functools
import os


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
        params.update(self._normalize(item))
        params.update(self._normalize(kwargs))
        try:
            issue = self.jira.create_issue(**params)
        except:
            print params
            raise
        return issue

    def compute_defaults(self):
        params = {}
        for m in self.manifests:
            params.update(self._normalize(m))
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
                item.pop(k, v)
        return item


def connect(server=None, username=None, password=None):
    def _value(name, value):
        return value or os.environ['JY_%s' % name.upper()]

    return GreenHopper(options={'server': _value('server', server)},
                       basic_auth=(_value('username', username),
                                   _value('password', password)))


def main():
    parser = OptionParser()
    parser.add_option("-t", "--test",
                      action="store_true", dest="test", default=False,
                      help="test mode")
    parser.add_option("-O", "--output",
                      dest="output", default=None,
                      help="output file", metavar="OUTFILE")

    (options, args) = parser.parse_args()

    if options.test:
        from mock import Mock
        jira = Mock(spec=GreenHopper)
        jira.search_issues.return_value = [Mock(), Mock()]

        def create_issue(**kwargs):
            m = Mock()
            m.key = kwargs
            return m
        jira.create_issue.side_effect = create_issue
        options.output = "/dev/stdout"
    else:
        jira = connect()
    infile = args[0]
    outfile = options.output or infile

    items = load(open(infile))

    context = Context(jira)

    defaults = os.path.expanduser("~/.jy")
    if os.path.exists(defaults):
        def_ = load(open(defaults))
        NewManifest(context)(def_)
    try:
        ApplyTransformers(context)(items)
    finally:
        with open(outfile, "w") as f:
            dump(items, f, default_flow_style=False)


if __name__ == '__main__':
    main()
