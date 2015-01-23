from collections import OrderedDict
from jira.utils import raise_on_error
from jy.ioutil import slist, sdict
import json
import urlparse


def safe_str(s):
    try:
        return str(s)
    except UnicodeEncodeError:
        return s


class TransformerMetaClass(type):
    # Metaprogramming/RegisterLeafClasses.py

    def __init__(cls, name, bases, nmspc):
        super(TransformerMetaClass, cls).__init__(name, bases, nmspc)
        if not hasattr(cls, 'registry'):
            cls.registry = set()
        cls.registry.add(cls)
        cls.registry -= set(bases) # Remove base classes
    # Metamethods, called on class objects:

    def __iter__(cls): #@NoSelf
        return iter(cls.registry)

    def __str__(cls): #@NoSelf
        if cls in cls.registry:
            return cls.__name__
        return cls.__name__ + ": " + ", ".join([sc.__name__ for sc in cls])


class Transformer(object):
    __metaclass__ = TransformerMetaClass

    priority = 100
    ignored = []

    def __init__(self, ctx):
        self.ctx = ctx

    def __call__(self, item):
        pass


class KeyTransformer(Transformer):
    """Base class for transformers which operate on a one or more keys."""
    keys = []

    def __call__(self, item):
        for k in self.keys:
            if k in item:
                self._do(k, item[k], item)


class ApplyTransformers(Transformer):
    priority = 10 ** 10
    ignored = ['items']

    def __call__(self, item):
        if isinstance(item, list):
            items = item
        else:
            items = item.get('items', [])

        transformers = [t(self.ctx) for t in sorted(Transformer, key=lambda x: x.priority)]
        original_manifest = list(self.ctx.manifests)
        for item in items[:]:
            for t in transformers:
                try:
                    t(item)
                except StopIteration:
                    break
        self.ctx.manifests = original_manifest


class UpdateIssues(object):
    """Updates fields on each item. Removes items from the document if they are completed,
    when purge option is set."""
    def __init__(self, context, purge=False):
        self.ctx = context
        self.purge = purge
        self.keys = {}

    def __call__(self, items):
        self.recurse(items)
        self.do_updates()

    def do_updates(self):
        search = DoSearch(self.ctx)._search("key in (%s)" % ",".join(self.keys.keys()))
        for _, v in search:
            item = self.keys[v['key']]
            item.apply('status', str(v['status']))
            self.on_update(item)

    def recurse(self, items):
        if isinstance(items, dict):
            items = [items]
        for item in items[:]:
            self.inspect(item)

    def inspect(self, item):
        if not item.get('key'):
            return
        self.keys[item['key']] = item
        for i in item.get('items', []):
            self.recurse(i)
        for i in item.get('subtasks', []):
            self.recurse(i)

    def on_update(self, item):
        if self.purge and item['status'] in ("Closed", "Resolved"):
            item.parent.remove(item)


class Skip(KeyTransformer):
    """Skip over this item."""
    priority = 0
    keys = ['+ignore', '-ignore']

    def _do(self, *args):
        raise StopIteration


class Section(KeyTransformer):
    keys = ignored = ['+section', '+block']

    def _do(self, k, _, item):
        if 'summary' in item:
            v = [("*" * 80), item['summary'], ("*" * 80)]
        else:
            v = [("*" * 80), ("*" * 80)]
        item.apply(k, v)


class AddComment(KeyTransformer):
    ignored = keys = ['+comment']

    def _do(self, k, comment, item):
        self.ctx.jira.add_comment(item['key'], comment)
        item.rm(k)
        print "Added to", item['key'], comment


class SetStatus(KeyTransformer):
    ignored = keys = ['+status']
    transitions = {}

    def _do(self, k, status, item):
        prefix = item['key'].split('-')[0]
        if prefix not in self.transitions:
            trans = self.ctx.jira.transitions(item['key'])
            self.transitions[prefix] = dict([(t['name'], t['id']) for t in trans])
        try:
            self.ctx.jira.transition_issue(item['key'], self.transitions[prefix][status])
        except KeyError:
            print self.transitions[prefix]
            raise
        item.rm(k)
        item.apply('status', status)
        print "Updated status", item['key'], status


class SetFixVersion(KeyTransformer):
    ignored = keys = ['+fixVersion']

    def _do(self, k, name, item):
        issue = self.ctx.jira.issue(item['key'], fields='key')
        issue.update(dict(fixVersions=[dict(name=name)]))
        item.rm(k)
        item.apply('fixVersions', name)
        print "Updated fixVersion", item['key'], name


class IssueLinks(KeyTransformer):
    priority = 1000
    ignored = keys = ['links']

    def _do(self, _k, links, item):
        if 'key' not in item:
            return

        for i, link in enumerate(links):
            if 'created' in link:
                continue
            if isinstance(link, basestring):
                link = {link: 'relates to'}
            issue, type_ = link.items()[0]
            self.ctx.jira.create_issue_link(type_, item['key'], issue)
            link.apply('created', True)
            print "Linked", item['key'], "to", issue


class ParentLink(Transformer):
    priority = 1000

    def __call__(self, item):
        if not item.get('created'):
            return
        parent = item.parent.parent
        if not parent:
            print "No parent", item.parent.parent
            return
        type_ = parent['issuetype']
        if isinstance(type_, dict):
            type_ = type_['name']
        if type_ == 'Epic':
            self.ctx.jira.add_issues_to_epic(parent['key'], [item['key']])
            print "Linked issue to Epic", parent['key'], "<-", item['key']
        else:
            self.ctx.jira.create_issue_link("relates to", item['key'], parent['key'])
            print "Linked", item['key'], "to", parent['key']


class SprintLink(KeyTransformer):
    priority = 1000

    ignored = keys = ['sprint', '+sprint']
    boards = {}
    sprints = {}

    @classmethod
    def add_board(cls, board_id_or_url):
        if 'http' in str(board_id_or_url):
            board_id = urlparse.parse_qs(urlparse.urlparse(board_id_or_url).query)['rapidView'][0]
        else:
            board_id = board_id_or_url
        cls.boards[int(board_id)] = None

    def _do(self, key, sprint, item):
        # only work with items just created
        if not item.get('created') and key == 'sprint':
            return
        for board, sprints in self.boards.items():
            if sprints == None:
                self.boards[board] = set(self.ctx.jira.sprints(board))
                for sprint_ in self.boards[board]:
                    self.sprints[sprint_.name] = sprint_.id
        if sprint != 'backlog':
            print "Found sprint", sprint, self.sprints[sprint]
            sprint_name = sprint
            sprint = self.sprints[sprint]
        else:
            sprint_name = sprint
        add_issues_to_sprint(self.ctx.jira, sprint, [item['key']])
        print "Added", item['key'], "to", sprint_name
        if key == '+sprint':
            item.rm(key)
        item.apply('sprint', sprint_name)


def add_issues_to_sprint(self, sprint_id, issue_keys):
    """
    See comment thread here: https://confluence.atlassian.com/pages/viewpage.action?pageId=395707016

    Add the issues in ``issue_keys`` to the ``sprint_id``. The sprint must
    be started but not completed.

    If a sprint was completed, then have to also edit the history of the
    issue so that it was added to the sprint before it was completed,
    preferably before it started. A completed sprint's issues also all have
    a resolution set before the completion date.

    If a sprint was not started, then have to edit the marker and copy the
    rank of each issue too.

    :param sprint_id: the sprint to add issues to
    :param issue_keys: the issues to add to the sprint
    """
    data = {}
    data['idOrKeys'] = issue_keys
    data['customFieldId'] = 10002
    if sprint_id != 'backlog':
        data['sprintId'] = sprint_id
        data['addToBacklog'] = False
    else:
        data['addToBacklog'] = True 
    url = self._get_url('sprint/rank', base=self.GREENHOPPER_BASE_URL)
    r = self._session.put(url, data=json.dumps(data))
    raise_on_error(r)


class Subtasks(KeyTransformer):
    """Create subtasks"""
    ignored = keys = ['subtasks']

    def _do(self, _, tasks, item):
        for i, task in enumerate(tasks or []):
            if 'key' in task:
                continue
            st = self.ctx.create_subtask_from_item(task, item)
            print "Created", st.key
            item['subtasks'][i].apply('key', str(st.key))


class NewIssue(Transformer):
    """Create an issue from an item."""
    priority = 10

    issuetypes = ['Improvement', 'Project', 'Story', 'Bug', 'Epic', None]

    def __call__(self, item):
        for k in self.issuetypes:
            if k in item:
                break
        if k is None:
            return
        if k == 'Epic':
            if 'summary' not in item:
                item['summary'] = item[k]
            item['epicName'] = item.pop(k)
        else:
            item['summary'] = item.pop(k)
        item['issuetype'] = k

        if 'key' in item:
            return
        issue = self.ctx.create_issue_from_item(item)
        item.apply('key', str(issue.key))
        # for this session
        item['created'] = True
        print "Created", issue.key


class NewManifest(KeyTransformer):
    priority = 10 ** 5 # ensure this happens after any creation logic.

    ignored = keys = ['manifest', 'aliases', 'userAliases', 'userFields', 'objectify', 'sprintBoard', 'sprintBoards']

    def __init__(self, ctx):
        super(NewManifest, self).__init__(ctx)
        self.current = None
        self._sprints = None
        self.boards = []

    def _do(self, key, manifest, _):
        if key == 'aliases':
            self.ctx.aliases.update(manifest)
        elif key == 'userFields':
            self.ctx.user_fields.extend(manifest)
        elif key == 'userAliases':
            self.ctx.user_aliases.update(manifest)
        elif key == 'objectify':
            for k, v in manifest.items():
                self.ctx.update_objectified(k, v)
        elif key == 'sprintBoard':
            SprintLink.add_board(manifest)
        elif key == 'sprintBoards':
            [SprintLink.add_board(board_id) for board_id in manifest]
        elif key == 'manifest':
            if self.current:
                # we are seeing a second manifest at the same depth
                self.ctx.manifests.pop()
            # this is the first manifest in this series
            self.ctx.manifests.append(manifest)
            self.current = manifest


class DoSearch(Transformer):
    def __call__(self, item):
        """Expands a node which declares a search.
        """
        if 'search' not in item:
            return
        if item.get('complete'):
            return
        item.apply('complete', True)
        i_ = item.parent.index(item)
        for j, data in self._search(item['search']):
            item.parent.insert(i_ + 2 + j, sdict(data.items()))

    def _search(self, query):
        for j, issue in enumerate(self.ctx.jira.search_issues(query, maxResults=200)):
            data = OrderedDict()
            type_ = str(issue.fields.issuetype.name)
            data[type_] = safe_str(issue.fields.summary)
            data['assignee'] = str(issue.fields.assignee.name)
            data['status'] = str(issue.fields.status.name)
            data['desc'] = safe_str(issue.fields.description)
            data['key'] = str(issue.key)
            yield j, data


class GetLinked(KeyTransformer):
    ignored = keys = ['+linked']

    def _do(self, _k, query, item):
        search = DoSearch(self.ctx)
        parent = item.parent.parent
        i_ = item.parent.index(item)
        key = parent['key']
        q = "(issue in linkedIssues(%s) or \"Epic Link\" = %s or parent = %s)" % (key, key, key)
        if query:
            q = "%s AND %s" % (q, query)
        for j, data in search._search(q):
            item.parent.insert(i_ + 2 + j, sdict(data.items()))
        item.parent.remove(item)
