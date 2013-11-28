"""

                                                    Suit Template Engine
@author:    Andrey Yurjev (ayurjev)
@date:      26.11.2013
@version:   1.1

#################################################       Suit scheme:          ##########################################

                            Programmer                                       Client
*                                V                           *                  |
*                        Source Templates                    *                  |
*                                |                           *                  |
*                                V                           *                  |
*                            Compiler                        *                  |
*                                |                           *                  |
*                                V                           *                  |
*                            Template                        *                  |
*                                |                           *                  |
*                                V                           *                  |
* XmlTag  <-----------------> TemplatePart                   *                  |
*    SuitTag                     |                           *                  V
*        Variable                |                           *              Suit/suit
*        Condition               |                           *                  |
*        ...                     |                           *                  |
*            |                   V                           *                  V                       SuitNone
*            V--------------> SyntaxEngine           -----------------> Compiled Templates <----------- SuitFilters
*                                PythonSyntaxEngine          *                  |                       SuitRuntime
*                                JavascriptSyntaxEngine      *                  |
*                                ...                         *                  V
*                                                            *                 HTML
*                                                            *
***********************************************************************************************************************
"""

import re
import os
import json
import importlib
from abc import ABCMeta, abstractmethod
from datetime import datetime, date, time


SuitTags = [
    "var", "if", "list", "breakpoint", "expression", "condition", "true", "false", "iterationvar", "iterationkey"
]


class TemplateParseError(Exception):
    pass


class TagCounter(object):
    """ Counts/decounts a nested tags """

    def __init__(self):
        self.maxI = 0

    def count(self, expression):
        """
        Enumerates all the tags found in given expression, so <p><p></p></p> becomes <p_1><p_2></p_2></p_1>
        :param expression:  Expression with some tags inside
        :return:            Enumerated result
        """
        try:
            stack = []
            self.maxI = 0
            p = re.compile("<(/*(%s))(\s|>)+" % "|".join(SuitTags), re.DOTALL)
            return re.sub(p, lambda tagMatch: self._manageStack(tagMatch, stack), expression)
        except IndexError:
            raise TemplateParseError("opening/closing tags missmatch found: %s" % expression)

    def decount(self, template):
        """
        Cleans up all enumerations from tags
        :param template:  Enumerated template
        :return:          Cleaned template
        """
        template = re.sub("<\w+(_\d+)[\s|>]+", lambda m: m.group(0).replace(m.group(1), ""), template)
        template = re.sub("</\w+(_\d+)>", lambda m: m.group(0).replace(m.group(1), ""), template)
        return template

    def _manageStack(self, tagMatch, stack):
        """
        Controls the stack of opening/closing brackets during the count() operation
        :param tagMatch: Founded tag (opening or closing)
        :param stack:    Current stack
        :return:
        """
        tagMatch, tag = tagMatch.group(0), tagMatch.group(1)
        if tag.startswith("/"):
            return tagMatch.replace(tag, "%s_%s" % (tag, stack.pop()))
        else:
            newI = self.maxI
            stack.append(newI)
            self.maxI += 1
            return tagMatch.replace(tag, "%s_%s" % (tag, newI))


class XmlTag(object):
    """
    Base class of the tags hierarchy.
    It represents a ordinary xml tag without any template engine logic.
    """
    def __init__(self, stringTag):
        self.stringTag = re.sub("\s\s+", " ", stringTag).strip()
        self.firstLine = self.parseFirstLine(self.stringTag)
        self.name = self.parseTagName(self.firstLine)
        self.attributes = self.parseAttributes(self.firstLine)
        self.body = self.parseBody(self.name, self.firstLine, self.stringTag)
        self.name = self.name.split("_")[0]

    def get(self, attrName):
        """
        Returns an attribute value by given attribute name
        :param attrName: name of the attribute
        :return:         attribute value
        """
        return self.attributes.get(attrName)

    def parseFirstLine(self, expression):
        """
        Returns the first line of the tag (opening part between < and > with all attributes)
        :return: str:
        """
        firstLine, stack, quotes_opened1, quotes_opened2 = "", 0, False, False
        for char in expression:
            if char == "<" and (quotes_opened1 is False and quotes_opened2 is False):
                stack += 1
            elif char == ">" and (quotes_opened1 is False and quotes_opened2 is False):
                stack -= 1
                if stack == 0:
                    firstLine += char
                    break
            elif char == "'":
                quotes_opened1 = quotes_opened1 is False
            elif char == '"':
                quotes_opened2 = quotes_opened2 is False
            firstLine += char
        return firstLine

    def parseTagName(self, firstLine):
        """ Returns name of the tag """
        return self._map_replace(firstLine.split(" ")[0], {"<": "", ">": ""})

    def parseAttributes(self, firstLine):
        """ Returns attributes of the tag in a map """
        result = {}
        matches = re.findall('''\s(.+?)=(?P<quote>\"|')(.*?)(?P=quote)+''', firstLine, re.DOTALL)
        if len(matches) > 0:
            for match in matches:
                result[match[0]] = match[2]
        return result

    def parseBody(self, tagName, firstLine, expression):
        """ Returns body of the tag represented by TemplatePart instance """
        return self._map_replace(expression, {firstLine: "", "</%s>" % tagName: ""}).strip()

    def _map_replace(self, string, repl_map):
        for hs in repl_map:
            string = string.replace(hs, repl_map[hs])
        return string


class Variable(XmlTag):
    """ Represents an ordinary variables """

    def __init__(self, tag_string):
        super().__init__(tag_string)
        self.var_name = self._convertVarPath(self.body)
        self.default = self.attributes.get("d")
        self.filters = self.get_filters()

    def get_filters(self):
        """
        Returns a list of the (filterName, filterParams) that should be applied to the variable
        :return: list:
        """
        filters = self.attributes.get("filter") or ""
        result = [(f.strip(), self.attributes.get("%s-data" % f.strip())) for f in filters.split(",")]
        return list(filter(lambda it: it[0] not in [None, "None", ""], [(f[0], f[1]) for f in result]))

    def _convertVarPath(self, varDottedNotation):
        """
        Converts the call to a variable from dot-notation to brackets-notation
        :param varDottedNotation:   Variable    user.name
        :return:                    Result      ["user"]["name"]
        """
        varDottedNotation = varDottedNotation.strip(".")
        varDottedNotation = varDottedNotation.replace(".[", "[")
        varDottedNotation = re.sub("\.+", ".", varDottedNotation)
        tmp = re.sub('''\[.+\]''', lambda m: "." + m.group(0), varDottedNotation)
        tmp = tmp.replace(".[", '''"][''')
        tmp = tmp.replace("].", ''']["''')
        tmp = tmp.replace(".", '''"]["''')
        result = '''["''' + tmp + ('''"]''' if tmp.endswith("]") is False else "")
        return result


class IterationVariable(Variable):
    """ Represents an iteration variable """
    def _convertVarPath(self, varDottedNotation):
        # we dont interested in parameter varDottedNotation
        # since we have all required data in attributes of current tag
        varDottedNotation = ".".join(
            list(
                filter(
                    lambda m: m != "None",
                    [self.attributes.get("in"), self.attributes.get("name"), self.attributes.get("path")]
                )
            )
        )
        res = super()._convertVarPath(varDottedNotation)
        res = re.sub('\["%s"\]' % self.attributes.get("name"), '[%s]' % self.attributes.get("name"), res)
        return res


class IterationKey(Variable):
    """ Represents an iteration key """
    def __init__(self, tag_string):
        super().__init__(tag_string)
        self.var_name = self.attributes.get("name") + (
            self.attributes.get("mod") if self.attributes.get("mod") is not None else ""
        )


class Condition(XmlTag):
    """ Represents a condition expression """
    def __init__(self, tagString):
        super().__init__(tagString)
        self.condition = TemplatePart(
            self.attributes.get("condition")
        ) if self.attributes.get("condition") is not None else None

        self.true = TemplatePart(self.body)
        self.false = TemplatePart("")
        for t in TemplatePart(self.body).getTags():
            if t.name == "condition":
                self.condition = TemplatePart(t.body)
            elif t.name == "true":
                self.true = TemplatePart(t.body)
            elif t.name == "false":
                self.false = TemplatePart(t.body)


class Expression(XmlTag):
    """ Represents a simple expression that can be avaluated """
    def __init__(self, tag_string):
        super().__init__(tag_string)
        self.expresion_body = TemplatePart(self.body)


class List(XmlTag):
    """ Represents an iteration cycle """

    def __init__(self, tagString):
        super().__init__(tagString)
        # parsing itervar
        itervar = self.attributes.get("for")
        if itervar.find(",") > -1:
            self.dict_iteration = True
            self.iterkey, self.iterval = itervar.replace(" ", "").split(",")
        else:
            self.dict_iteration = False
            self.iterkey, self.iterval = itervar, itervar

        # parsing iterable
        iterable = self.attributes.get("in")
        if iterable.startswith("<var"):
            self.iterable = Variable(iterable)
            self.iterable_name = Variable(iterable).body
        else:
            self.iterable = Variable("<var>%s</var>" % iterable)
            self.iterable_name = iterable

        # parsing template
        self.iteration_template = TemplatePart(self.rename_iteration_variables(self.body))

    def rename_iteration_variables(self, template):
        # converting nested lists iterables
        template = re.sub(
            '''\sin=["|']%s(.*?)["|']''' % self.iterval,
            lambda m: " in='%s[%s]%s'" % (
                self.iterable_name,
                self.iterkey if self.iterkey is not None else self.iterval,
                m.group(1)
            ),
            template
        )

        # iteration counter
        template = re.sub(
            "<var(?P<counter>([_\d])*)>i</var(?P=counter)>",
            lambda m: "<iterationkey type='key' mod=' + 1' name='%s'></iterationkey>" % self.iterval,
            template
        )

        # converting itervals
        template = re.sub(
            "<var(?P<counter>(?:[_\d])*)(\s.*)*>%s([.|\[]+.*)*</var(?P=counter)>" % self.iterval,
            lambda m: "<iterationvar type='value' in='%s' name='%s' path='%s'%s></iterationvar>" % (
                self.iterable_name,
                self.iterkey if self.iterkey is not None else self.iterval,
                m.group(3),
                m.group(2) if m.group(2) is not None else ""
            ),
            template
        )

        # converting iterkeys
        if self.dict_iteration:
            template = re.sub(
                "<var(?P<counter>(?:[_\d])*)>%s</var(?P=counter)>" % self.iterkey,
                lambda m: "<iterationkey type='key' name='%s'></iterationkey>" % self.iterkey,
                template
            )
        return template


class Breakpoint(XmlTag):
    def __init__(self, tag_string):
        super().__init__(tag_string)
        self.isInclude = self.attributes.get("include") is not None
        self.template_name = self.attributes.get("include")
        self.content = TemplatePart(self.body)
        self.template_data = TemplatePart(
            self.attributes.get("data")
        ) if self.attributes.get("data") is not None else None


SuitTagsMap = {
    "var": Variable, "iterationvar": IterationVariable, "iterationkey": IterationKey,
    "if": Condition, "list": List, "expression": Expression, "breakpoint": Breakpoint
}


class TemplatePart(object):
    """
    Class TemplatePart.
    Represents any kind of textual content with some tags inside or without
    For example,
    "hello<span>, </span>world!" is not valid xml-tag,
    but it's a normal TemplatePart string
    """
    def __init__(self, text, tags_to_process=None):
        text = trimSpaces(text)
        self.text = text
        self.cdata = []
        self.tags = None
        self.tags_pattern = None
        self.tags_counter = TagCounter()

        if tags_to_process is None:
            tags_to_process = SuitTags
        self.parseTags(tags_to_process)

    def parseTags(self, tags_to_process):
        """
        Defines tags to be parsed from template
        :param: list:   tags_to_process:    List of tag names to be parsed from template
        """
        self.tags = tags_to_process
        self.tags_pattern = re.compile(
            '<(?P<tagName>(?:%s)+([_\d])*)(?:\s.+?)*>(?:.?)*</(?P=tagName)>' % (
                "|".join(tags_to_process)
            ), re.DOTALL
        )
        self.text = re.sub(
            self.tags_pattern,
            lambda m: "{{ph:%d}}" % (self.cdata.append(m.group(0)) or len(self.cdata) - 1),
            self.tags_counter.count(self.text)
        )

    def getText(self):
        """
        Retruns a string representing template.
        If template part had some tags inside and they were defined by setTags() - result of getText() will be
        template string, where any occurancies of that tags will be replaced by "%s" placeholder
        :return: string
        """
        return self.text

    def getData(self):
        """
        Returns a list of all tags found in Template Part and defined by setTags() method
        :return: list
        """
        return self.cdata

    def getTags(self):
        """
        Returns a list of the XmlTag objects corresponding to getData() method
        :return:
        """
        return [self.toSuitTag(tag_text) for tag_text in self.cdata]

    def getDataForCompile(self):
        """
        Returns a tuple (text, tags) for compiler
        :return: tuple
        """
        return self.getText(), self.getTags()

    def toSuitTag(self, tag_text):
        name = tag_text.split(" ")[0].split(">")[0].replace("<", "").split("_")[0]
        suit_tag = SuitTagsMap.get(name) or XmlTag
        return suit_tag(tag_text)


class Template(object):

    def __init__(self, templateName):
        self.tags_counter = TagCounter()
        self.templateName = templateName
        f = open(templateName)
        self.content = "".join(f.readlines())
        f.close()
        self.content = re.sub("<!--(.+?)-->", "", self.content)         # cut all comments
        self.css, self.js = None, None
        self.parse_resources("css", "<style(?:\s.+?)*>(.*?)</style>")   # cut & save css
        self.parse_resources("js", "<script>(.*?)</script>")            # cut & save js
        self.rebase()
        self.include()

    def getContent(self):
        return self.content

    def getBreakPoints(self, all_levels=False, content=False):
        """
        Returns a map of all breakpoints found in template.
        Use all_levels = True for recursion

        :param all_levels:  Do we need to look deeper than one level of nested tags
        :param content:     Content to be parsed
        :return: dict:      map of breakpoints {name: tag}
        """
        if content is False:
            content = self.content
        content = self.tags_counter.count(content)
        breakpointsMap = {}
        bps = re.findall('(<breakpoint(?P<brcount>[_\d]*)(?:\s.+?)*>.+?</breakpoint(?P=brcount)>)', content, re.DOTALL)
        for bp in bps:
            bp_element = Breakpoint(bp[0])
            if bp_element.get("name"):
                breakpointsMap[bp_element.get("name")] = self.tags_counter.decount(bp[0])
                if all_levels:
                    nextLevel = self.getBreakPoints(all_levels, bp_element.body)
                    for bpname in nextLevel:
                        breakpointsMap[bpname] = nextLevel[bpname]
        return breakpointsMap

    def parse_resources(self, res_type, regexp):
        """ Excludes all css styles from template and stores them in self """
        match = re.search(regexp, self.content, re.DOTALL)
        if match is not None:
            self.content = self.content.replace(match.group(0), "")
            self.__dict__[res_type] = match.group(1)

    def rebase(self):
        """ Performs a rebase operation if template contains <rebase> tag """
        parentTemplateName = re.search('<rebase(?:\s.+?)*>(.+?)</rebase>', self.content, re.DOTALL)
        if parentTemplateName is None:
            return
        parent = Template(parentTemplateName.group(1).strip("'").strip("\"").replace(".", "/") + ".html")
        rebased_template = parent.content
        bp_parent = parent.getBreakPoints(all_levels=True)
        bp_current = self.getBreakPoints()
        for bp_name in bp_parent:
            if bp_current.get(bp_name):
                rebased_template = rebased_template.replace(bp_parent[bp_name], bp_current[bp_name])
        self.content = rebased_template

    def include(self):
        """ Includes all sub templates if template contains <breakpoint> tags with 'include' attribute """
        self.content = re.sub(
            '(<breakpoint(?P<brcount>(?:[_\d])*) include=(.+?)(?:\s.+?)*>.*</breakpoint(?P=brcount)>)',
            lambda m: Template(m.group(3).strip("'").strip("\"").replace(".", "/") + ".html").getContent(),
            self.content,
            re.DOTALL
        )

    def compile(self, languageEnginesMap):
        """
        Compiles itself into source code according given map
        :param languageEnginesMap:
        :return:
        """
        template_part = TemplatePart(self.content)
        compiled = {
            language: languageEnginesMap[language]().compile(
                template_part.getDataForCompile()
            ) for language in languageEnginesMap
        }

        # Compiling python source
        templateName = self.templateName.replace(".html", "").replace("/", "_")
        pythonSource = "from suit.Suit import Suit, SuitRunTime, SuitNone, SuitFilters\n" \
                       "class %s(object):\n" \
                       "\tdef execute(self, data={}):\n" \
                       "\t\tself.data = data\n" \
                       "\t\treturn (%s)" % (templateName, compiled["py"])
        f = open("__py__/%s" % self.templateName.replace("/", "_").replace("html", "py"), "w+")
        f.writelines(pythonSource)
        f.close()

        # Build css
        f = open("__css__/%s" % self.templateName.replace("/", "_").replace("html", "css"), "w+")
        f.writelines("".join(self.css or ""))
        f.close()

        # Build js
        jsCompiled = compiled["js"]
        jsApiInit = "null"
        if self.js:
            jsApiInit = '''function() {
                return %s()
            }''' % self.js.strip()

        jsSource = '''suit.SuitApi.addTemplate("%s", function(data) {
           if (data == null) { data = {}; };
           return %s
        }, %s);
            ''' % (self.templateName.replace(".html", "").replace("/", "."), jsCompiled, jsApiInit)

        f = open("__js__/%s" % self.templateName.replace("/", "_").replace("html", "js"), "w+")
        f.writelines(jsSource)
        f.close()


class Syntax(metaclass=ABCMeta):
    """ Abstract Class For Creating Language Engines """
    def try_compile(self, text):
        """ Tries to compile given string """
        if text is not None:
            return self.compile(TemplatePart(text).getDataForCompile())

    def compile_tag(self, tag):
        """ Compiles given SuitTag into source code """

        if isinstance(tag, IterationKey):
            return tag.var_name

        elif isinstance(tag, IterationVariable):
            filters = [
                lambda var: self.filter(filter_name, var, self.try_compile(filter_data))
                for filter_name, filter_data in tag.filters
            ]
            return self.var(tag.var_name, filters, without_stringify=True)

        elif isinstance(tag, Variable):
            filters = [
                lambda var: self.filter(filter_name, var, self.try_compile(filter_data))
                for filter_name, filter_data in tag.filters
            ]
            return self.var(tag.var_name, filters, self.try_compile(tag.default))

        elif isinstance(tag, Condition):
            return self.condition(
                self.compile(tag.condition.getDataForCompile()),
                self.compile(tag.true.getDataForCompile()),
                self.compile(tag.false.getDataForCompile())
            )

        elif isinstance(tag, List):
            return self.list(
                self.compile(tag.iteration_template.getDataForCompile()),
                tag.iterkey,
                self.var(tag.iterable.var_name, without_stringify=True)
            )

        elif isinstance(tag, Expression):
            return self.expression(self.compile(tag.expresion_body.getDataForCompile()))

        elif isinstance(tag, Breakpoint):
            return self.compile(tag.content.getDataForCompile())

        else:
            raise None

    @abstractmethod
    def compile(self, data):
        pass

    @abstractmethod
    def convertplaceholders(self, template):
        pass

    @abstractmethod
    def var(self, var_name, filters=None, default=None, without_stringify=False):
        pass

    @abstractmethod
    def condition(self, condition, true, false):
        pass

    @abstractmethod
    def list(self, template, itervar, iterable):
        pass

    @abstractmethod
    def expression(self, expression):
        pass

    @abstractmethod
    def filter(self, filterName, var, data=None):
        pass

    def logicand(self):
        return "&&"

    def logicor(self):
        return "||"

    def true(self):
        return "true"

    def false(self):
        return "false"


class PythonSyntax(Syntax):
    """
    Класс, обеспечивающий возможность компиляции шаблонов в исходный код python
    """

    def compile(self, data):
        template, tags = data
        template = template.replace('"', '\\"')
        template = self.convertplaceholders(template)
        template = re.sub("(%[^sdmiHMyS])", lambda m: "%%%s" % m.group(1), template)
        if len(tags) > 0:
            return '"' + template + '" % (' + ", ".join([self.compile_tag(t) for t in tags]) + ')'
        else:
            return ('"' + template + '"').replace("%%", "%")

    def convertplaceholders(self, template):
        return re.sub("\{\{ph:\d\}\}", "%s", template)

    def var(self, var_name, filters=None, default=None, without_stringify=False):
        if filters is None:
            filters = []
        res = "SuitRunTime.var(lambda self: self.data%s, %s, self)" % (var_name, default)
        for filter_lambda in filters:
            res = filter_lambda(res)
        if without_stringify is False:
            return "SuitRunTime.stringify(%s)" % res
        else:
            return res

    def condition(self, condition, true, false):
        condition = condition.replace("&&", self.logicand())
        condition = condition.replace("||", self.logicor())
        condition = condition.replace("true", self.true())
        condition = condition.replace("false", self.false())
        return '''SuitRunTime.opt(%s, lambda: %s, lambda: %s)''' % (condition, true, false if false else "")

    def list(self, template, itervar, iterable):
        return '''SuitRunTime.list(lambda %s: %s, %s)''' % (itervar, template, iterable)

    def expression(self, expression):
        return "SuitRunTime.expression(%s)" % expression

    def filter(self, filterName, var, data=None):
        if data is None:
            return '''SuitFilters._%s(%s)''' % (filterName, var)
        else:
            return '''SuitFilters._%s(%s, %s)''' % (filterName, var, data)

    def logicand(self):
        return "and"

    def logicor(self):
        return "or"

    def true(self):
        return "True"

    def false(self):
        return "False"


class JavascriptSyntax(Syntax):
    """
    Класс, обеспечивающий возможность компиляции шаблонов в исходный код javascript

    """
    def compile(self, data):
        template, tags = data
        template = template.replace('"', '\\"')
        template = self.convertplaceholders(template)
        if len(tags) > 0:
            return '"' + template + '".format(' + ", ".join([self.compile_tag(t) for t in tags]) + ')'
        else:
            return '"' + template + '"'

    def convertplaceholders(self, template):
        return re.sub('\{\{ph:(\d)\}\}', lambda m: "{%s}" % m.group(1), template)

    def var(self, var_name, filters=None, default=None, without_stringify=False):
        if filters is None:
            filters = []
        res = "suit.SuitRunTime.var(function(){ return data%s; }, %s)" % (
            var_name, default if default is not None else "null"
        )
        for filter_lambda in filters:
            res = filter_lambda(res)
        return res if without_stringify else "suit.SuitRunTime.stringify(%s)" % res

    def condition(self, condition, true, false):
        return 'suit.SuitRunTime.opt(%s, function() {return (%s)}, function() {return (%s)})' % (condition, true, false)

    def list(self, template, itervar, iterable):
        return '''suit.SuitRunTime.list(function(%s) { return %s; }, (%s))''' % (
            itervar, template.replace(".%s)" % itervar, "[%s])" % itervar), iterable)

    def expression(self, expression):
        return "eval(%s)" % expression

    def filter(self, filterName, var, data=None):
        if filterName == "length":
            var = '''suit.SuitFilters.length(%s, %s)''' % (var, var)
        elif filterName == "startswith":
            var = "suit.SuitFilters.startswith(%s, %s)" % (var, data)
        elif filterName == "in":
            var = "suit.SuitFilters.inArray(%s, %s)" % (var, data)
        elif filterName == "notin":
            var = "!suit.SuitFilters.inArray(%s, %s)" % (var, data)
        elif filterName == "contains":
            var = "suit.SuitFilters.contains(%s, %s)" % (var, data)
        elif filterName == "bool":
            return "suit.SuitFilters.bool(%s)" % var
        elif filterName == "int":
            return "suit.SuitFilters.int(%s)" % var
        elif filterName == "str":
            return '''suit.SuitFilters.str(%s)''' % var
        elif filterName == "dateformat":
            return '''suit.SuitFilters.dateformat(%s, %s)''' % (var, data)
        var = "suit.SuitRunTime.stringify(%s)" % var
        return var


class Compiler(object):

    def compile(self, path="."):
        """
        Компилирует все найденные шаблоны внутри указанного каталога

        :param path:    Путь до каталога с шаблонами
        """
        self._checkCompiledPackage()
        for file in os.listdir(path):
            target = (path + "/" + file) if path != "." else file
            if os.path.isdir(target):
                self.compile(target)
            elif os.path.isfile(target):
                if self._isTemplateName(target) is False:
                    continue
                template = Template(target)
                template.compile({"py": PythonSyntax, "js": JavascriptSyntax})

    def build(self):
        """
        Собирает js-шаблоны в билды согласно их размещению в каталогах

        """
        for file in os.listdir("."):
            if os.path.isdir(file):
                self._build_catalog(file, "js")
                self._build_catalog(file, "css")
        self._build_all("js")
        self._build_all("css")

    def _build_all(self, fileType):
        """
        Собирает общую библиотеку всех fileType-файлов

        """
        all_content = []
        for file in os.listdir("__%s__" % fileType):
            if os.path.isfile("__%s__/" % fileType + file) and \
                    file.endswith(".%s" % fileType) and \
                    file.startswith("all.") is False:
                f = open("__%s__/%s" % (fileType, file))
                all_content += f.readlines()
                f.close()

        f = open("__%s__/all.%s" % (fileType, fileType), "w+")
        f.writelines("".join(all_content))
        f.close()

    def _build_catalog(self, path, fileType):
        """
        Собирает шаблоны внутри каталога в единый файл, готовый для подключения к проекту

        :param path:      Каталог, внутри которого необходимо собрать шаблоны
        """
        if path.startswith("__"):
            return

        path = path.strip("/")

        for file in os.listdir(path):
            if os.path.isdir(path + "/" + file):
                self._build_catalog(path + "/" + file, fileType)

        files = os.listdir("__%s__" % fileType)
        content = []
        for file in files:
            if file.startswith(path.replace("/", "_")) & file.endswith(fileType):
                f = open("__%s__/%s" % (fileType, file))
                content += f.readlines()
                f.close()

        f = open("__%s__/all.%s.%s" % (fileType, path.replace("/", "."), fileType), "w+")
        f.writelines("".join(content))
        f.close()

    def _checkCompiledPackage(self):
        """
        Проверяет наличие каталога __py__ и файла __init__.py в нем
        Создает в случае остутствия

        """
        os.chmod("../views/", 0o777)

        if os.path.isfile("__init__.py") is False:
            f = open("__init__.py", "w+")
            f.close()

        if os.path.isdir("__js__") is False:
            os.mkdir("__js__")
            os.chmod("__js__", 0o777)

        if os.path.isdir("__py__") is False:
            os.mkdir("__py__")
            os.mkdir("__py__/__pycache__")
            os.chmod("__py__", 0o777)
            os.chmod("__py__/__pycache__", 0o777)

        if os.path.isdir("__css__") is False:
            os.mkdir("__css__")
            os.chmod("__css__", 0o777)

        if os.path.isdir("__pycache__") is False:
            os.mkdir("__pycache__")
            os.chmod("__pycache__", 0o777)

        if os.path.isfile("__py__/__init__.py") is False:
            f = open("__py__/__init__.py", "w+")
            f.close()

    def _isTemplateName(self, path):
        """
        Проверяет корректность параметра path, если подразумевается, что path - это путь до исходника шаблона

        :param path:    Путь до шаблона
        :raise:         InvalidCompilerOptionsException
        """
        if path.endswith(".html") is False or os.path.isfile(path) is False:
            return False


########################################### RunTime Classes ##########################################################


class Suit(object):
    """
    Suit execution wrapper
    """
    def __init__(self, templateName):
        templateClassName = templateName.replace(".", "_")
        module = importlib.import_module("views.__py__.%s" % templateClassName)
        templateClass = getattr(module, templateClassName)
        self.template = templateClass()

    def execute(self, data=None):
        """
        Executes a template
        :param data: data for template execution
        :return:     result of template execution
        """
        if data is None:
            data = {}
        return self.template.execute(data)


def suit(templateName):
    """ Suit decorator """
    def decorator(func):
        def wrapped(*args, **kwargs):
            data = func(*args, **kwargs)
            if isinstance(data, str) and len(data) > 0:
                return data
            elif isinstance(data, dict) is True:
                return Suit(templateName).execute(data)
            else:
                try:
                    return Suit(templateName).execute()
                except KeyError:
                    return data
                except NameError:
                    return data
        return wrapped
    return decorator


class SuitRunTime(object):
    """ RunTime helpers """
    @staticmethod
    def stringify(obj):
        """ Prints variable """
        return json.dumps(obj, default=json_dumps_handler) if type(obj) in [list, dict] else obj

    @staticmethod
    def var(lambdavar, default, context):
        """
        Calls variable in safe way, avoids exceptions and return SuitNone() in case of missing required variable
        :param lambdavar:  lambda function, which should return a variable's value
        :param default:    default value
        :param context:    execution context (object that contains template's data in it's attributes)
        """
        def safedefault():
            """ Returns default value or SuitNone() """
            return default if default is not None else SuitNone()
        try:
            res = lambdavar(context)
            if res is None:
                return safedefault()
            return res
        except NameError:
            return safedefault()
        except KeyError:
            return safedefault()
        except IndexError:
            return safedefault()
        except TypeError:
            return safedefault()

    @staticmethod
    def opt(condition, true, false):
        """
        Returns the result depending on evaluating of the condition
        :param condition:   string condition
        :param true:        lambda function used if condition is true
        :param false:       lambda function used if condition is false
        :return:
        """
        return true() if eval(condition) else false()

    @staticmethod
    def list(iterationGenerator, iterable):
        """
        Returns the result of an iteration
        :param iterationGenerator:  lambda function that generates template on each cycle iteration
        :param iterable:            iterable object
        :return: str:               result of cycle
        """
        iterable = range(0, len(iterable)) if type(iterable) is list else iterable
        return "".join([iterationGenerator(itervar) for itervar in iterable])

    @staticmethod
    def expression(expression):
        """
        Evaluates an expression
        :param expression:          expression string
        :return:                    result of evaluation
        """
        return eval(expression)


class SuitFilters(object):
    """
    Базовый класс, предоставляющий функционал фильтров (декораторов) для применения к переменным

    """
    @staticmethod
    def _length(var):
        return len(str(var) if isinstance(var, int) is True else var) if var not in [None] else 0

    @staticmethod
    def _startswith(var, data=None):
        return var.startswith(data) if isinstance(data, SuitNone) is False else False

    @staticmethod
    def _in(var, data):
        return (var in data) if (isinstance(var, SuitNone) is False and isinstance(data, SuitNone) is False) else False

    @staticmethod
    def _notin(var, data):
        return SuitFilters._in(var, data) is False

    @staticmethod
    def _contains(haystack, needle):
        return SuitFilters._in(needle, haystack)

    @staticmethod
    def _bool(var):
        if str(var).lower() in ["false", "none", "", "0"] or isinstance(var, SuitNone):
            return False
        else:
            return bool(var)

    @staticmethod
    def _int(var):
        return int(var) if isinstance(var, SuitNone) is False else 0

    @staticmethod
    def _dateformat(var, format_str):
        return var.strftime(format_str)

    @staticmethod
    def _str(var):
        return '''"%s"''' % var


class SuitNone(object):
    """ Represents None, but with more complicated logic """
    def __init__(self, value=None):
        self.value = value

    def get(self, key):
        return self.value

    def __str__(self):
        return self.value if self.value is not None else "SuitNone()"

    def __getitem__(self, key):
        return SuitNone(self.value)

    def __len__(self):
        return 0

    def __gt__(self, other):
        return other < 0

    def __ge__(self, other):
        return other <= 0

    def __lt__(self, other):
        return other > 0

    def __le__(self, other):
        return other >= 0

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    def __iter__(self):
        for it in []:
            yield it

    def startswith(self, prefix):
        return False

    def strftime(self, format_str):
        return ""


def json_dumps_handler(obj):
    """ json dumps handler """
    if isinstance(obj, time):
        obj = datetime(1970, 1, 1, obj.hour, obj.minute, obj.second)
        return obj.ctime()
    if isinstance(obj, datetime) or isinstance(obj, date):
        return obj.ctime()
    return None


def json_loads_handler(data):
    """ json loads handler """
    import re
    from datetime import datetime
    for k, v in data.items():
        if isinstance(v, str) and re.search("\w\w\w[\s]+\w\w\w[\s]+\d[\d]*[\s]+\d\d:\d\d:\d\d[\s]+\d\d\d\d", v):
            try:
                data[k] = datetime.strptime(v, "%a %b %d %H:%M:%S %Y")
            except Exception as err:
                raise err
    return data


def trimSpaces(string):
    """ Trims multiple spaces from string, leaves just one space instead """
    string = string.replace("\t", "  ").replace("\n", "  ").replace("\r", "  ")
    string = re.sub(">\s\s+", ">", string)
    string = re.sub("\s\s+<", "<", string)
    string = re.sub("\s\s+", " ", string, flags=re.MULTILINE)
    string = string.strip(" ")
    return string
