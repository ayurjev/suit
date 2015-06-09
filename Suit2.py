import os


def namepath(name):
    return name.replace(".", "/") + ".html"


def readfile(filepath):
    if os.path.isfile(filepath):
        with open(filepath, "r") as f:
            return f.read()


class TemplateNotFound(Exception):
    pass


class Template(object):
    def __init__(self, name, path=None, source=None):
        assert not (path is not None and source is not None)

        if path is not None:
            source = readfile("{path}/{name}".format(path=path, name=namepath(name)))
            if source is None:
                raise TemplateNotFound(name)

        self.source = source

    def execute(self, data):
        pass
