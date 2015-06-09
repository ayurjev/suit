import unittest
from suit.Suit2 import Template, TemplateNotFound


class TestTemplate(unittest.TestCase):
    def test_init(self):
        self.assertRaises(AssertionError, Template, "a", path="templates", source="<var>b</var>")
        self.assertRaises(TemplateNotFound, Template, "b", "templates")

        self.assertEqual("<var>a</var>", Template("a", "templates").source)
        self.assertEqual("<var>a</var>", Template("a", source="<var>a</var>").source)

        self.assertIsNone(Template("").source)
        self.assertIsNone(Template("a").source)

