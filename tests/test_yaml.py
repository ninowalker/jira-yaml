from jy.ioutil import load, sdict, dump, slist
import StringIO
import unittest


class TestLoader(unittest.TestCase):
    s1 = """- a: 1
- foo:
    bar:
      baz:
        a: 1
        b: 2
      boom:
      - a: 1
      - b: 2
        """

    def test_read(self):
        v = load(StringIO.StringIO(self.s1))
        assert isinstance(v, slist)
        assert v.parent is None
        assert len(v) == 2
        d = v.pop(0)
        assert isinstance(d, sdict), d
        assert d.parent is None
        assert d.real is not None
        assert d['a'] == 1
        d = v.pop(0)
        assert d.parent is None
        foo = d['foo']
        bar = foo['bar']
        baz = bar['baz']
        boom = bar['boom']
        assert foo.parent is d
        assert bar.parent is foo, bar.parent
        assert baz.parent is bar
        assert len(baz) == 2
        assert boom.parent is bar
        assert len(boom) == 2
        assert boom[0].parent == boom

    def test_no_write_through(self):
        v = load(StringIO.StringIO(self.s1))
        d = v.pop(0)
        d['b'] = 2
        s2 = StringIO.StringIO()
        dump(d, s2)
        s2_str = s2.getvalue()
        v2 = load(StringIO.StringIO(s2_str))
        assert d.real == v2, (v2.real, d.real)
        assert d != v2

    def test_write_through(self):
        v = load(StringIO.StringIO(self.s1))
        d = v.pop(0)
        d.apply('b', 2)
        s2 = StringIO.StringIO()
        dump(d, s2)
        s2_str = s2.getvalue()
        v2 = load(StringIO.StringIO(s2_str))
        assert d.real == v2, (v2.real, d.real)
        assert d == v2
