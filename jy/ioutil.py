import collections
import yaml


class sdict(collections.OrderedDict):
    """A shadow data structure which maintains a copy of the original data
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

    def rm(self, key):
        del self[key]
        del self.real[key]

    def parentize(self):
        for v in self.values():
            if isinstance(v, (sdict, slist)):
                v.parent = self


class slist(list):
    def __init__(self, *args):
        super(slist, self).__init__(*args)
        self.parent = None

    def parentize(self):
        for v in self:
            if isinstance(v, (sdict, slist)):
                v.parent = self

# from:
# http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG
_seq_tag = yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG


def sdict_representer(dumper, data):
    return dumper.represent_mapping(_mapping_tag, data.real.iteritems())


def sdict_constructor(loader, node):
    d = sdict(loader.construct_pairs(node))
    d.parentize()
    return d


def slist_representer(dumper, data):
    return dumper.represent_sequence(_seq_tag, data)


def slist_constructor(loader, node):
    l = slist(loader.construct_sequence(node))
    l.parentize()
    return l


yaml.add_representer(sdict, sdict_representer)
yaml.add_representer(slist, slist_representer)
yaml.add_constructor(_mapping_tag, sdict_constructor)
yaml.add_constructor(_seq_tag, slist_constructor)

load = yaml.load
dump = yaml.dump
