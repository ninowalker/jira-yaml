

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


class ApplyTransformers(Transformer):
    priority = 10 ** 10
    ignored = ['items']

    def __call__(self, item):
        if isinstance(item, list):
            items = item
        else:
            items = item.get('items', [])

        transformers = sorted(Transformer, key=lambda x: x.priority)
        for item in items[:]:
            for t in transformers:
                try:
                    t(self.ctx)(item)
                except StopIteration:
                    break


class Skip(Transformer):
    priority = 0

    def __call__(self, item):
        if item.get('+ignore'):
            raise StopIteration


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
        for j, issue in enumerate(self.ctx.search_issues(item['search'])):
            data = dict(key=str(issue.key),
                        summary=str(issue.fields.summary),
                        assignee=str(issue.fields.assignee.name),
                        status=str(issue.fields.status.name))
            item.parent.insert(i_ + 2 + j, data)
