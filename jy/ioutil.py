import collections
import yaml


class sdict(collections.OrderedDict):
    """A shadow datastructure which maintains a copy of the original data
    in order, and maintains parent-hierarchy.
    """
    def __init__(self, pairs, parent=None):
        super(sdict, self).__init__(pairs)
        self.real = collections.OrderedDict(pairs)
        self.parent = parent

    def __getitem__(self, key):
        v = dict.__getitem__(self, key)
        if isinstance(v, (sdict, slist)):
            v.parent = self
        return v

    def apply(self, key, value):
        self.real[key] = self[key] = value


class slist(list):
    def __init__(self, *args):
        super(slist, self).__init__(*args)
        self.parent = None

    def __getitem__(self, key):
        v = list.__getitem__(self, key)
        if isinstance(v, (sdict, slist)):
            v.parent = self
            print ">>>", self
        return v

# from:
# http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG
_seq_tag = yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG


def sdict_representer(dumper, data):
    return dumper.represent_mapping(_mapping_tag, data.real.iteritems())


def sdict_constructor(loader, node):
    return sdict(loader.construct_pairs(node))


def slist_representer(dumper, data):
    return dumper.represent_sequence(_seq_tag, data.real)


def slist_constructor(loader, node):
    return slist(loader.construct_sequence(node))


yaml.add_representer(sdict, sdict_representer)
yaml.add_representer(slist, slist_representer)
yaml.add_constructor(_mapping_tag, sdict_constructor)
yaml.add_constructor(_seq_tag, slist_constructor)

load = yaml.load
dump = yaml.dump