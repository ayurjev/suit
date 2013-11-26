"""
    Unit tests for Suit template engine

"""

import unittest
import os
import re
import hashlib
import json
import subprocess
from datetime import datetime

from z9.Suit.Suit import XmlTag, PythonSyntax, JavascriptSyntax, Compiler, Suit, suit, trimSpaces, json_dumps_handler


class SuitTest(unittest.TestCase):
    """
    Unit-тесты шаблонизатора Suit

    """

    def setUp(self):
        """
        Настраиваем условия для каждого теста

        """
        self.c = Compiler()
        self.maxDiff = None

        if os.path.isdir("views") is False:
            os.mkdir("views")
        if os.getcwd().endswith("views"):
            os.chdir("..")
        self.clearDir("views")
        if os.path.isdir("views/subfolder") is False:
            os.mkdir("views/subfolder")

    def tearDown(self):
        """
        Уничтожаем следы активности тестов

        """
        if os.getcwd().endswith("views"):
            os.chdir("..")
        self.clearDir("views")
        if os.path.isdir("views") is True:
            os.rmdir("views")
        if os.path.isfile("current.js"):
            os.remove("current.js")

    def clearDir(self, path):
        """
        Рекурсивно удаляет файлы и каталоги внутри указанного каталога

        :param path: Путь до каталога
        """
        #return
        for file in os.listdir(path):
            if os.path.isfile(path + "/" + file) and file != "suitup":
                os.remove(path + "/" + file)
            elif os.path.isdir(path + "/" + file):
                self.clearDir(path + "/" + file)
                os.rmdir(path + "/" + file)

    def simulate(self, template, expected, data=None, name=None, filterForExecuted=None, debug=False):
        """
        Эмулирует запись шаблона в файл, его компиляцию и выполнение

        :param template:            Исходный текст шаблона
        :param data:                Данные для выполнения шаблона
        :param expected:            Ожидаемый результат выполнения
        :param name:                Имя, которое необходимо задать для скомпилированного шаблона
        :param filterForExecuted:   Фильтр для ожидаемого результата (Для избежания незначительной разницы)
        :param debug:               Режим отладки (При включенном режиме отладки печатается промежуточный код)

        """

        # Записываем шаблон во временный файл:
        fileName = name or hashlib.md5((template + str(datetime.now())).encode()).hexdigest()
        self.assertFalse(os.path.isfile("views/subfolder/%s.html" % fileName))
        f = open("views/subfolder/%s.html" % fileName, "w+")
        f.writelines(template)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/%s.html" % fileName))

        # Компилируем все имеющиеся шаблоны
        os.chdir("views")
        self.c.compile()
        os.chdir("../")

        if debug:
            # Получаем скомпилированный python ход
            f = open("views/__py__/subfolder_%s.py" % fileName)
            compiled_python = "".join(f.readlines())
            compiled_python = re.search("return \((.+)\)", compiled_python).group(1)
            f.close()
            print("PY: ", compiled_python)

        # Получам результат выполнения скомпилированного python кода
        executed_python = Suit("subfolder.%s" % fileName).execute(data)
        executed_python = filterForExecuted(executed_python) if filterForExecuted is not None else executed_python

        # Получаем скомпилированный js код
        f = open("views/__js__/subfolder_%s.js" % fileName)
        compiled_javascript = "".join(f.readlines())
        f.close()

        compiled_javascript = re.sub("\s\s+", "", compiled_javascript).replace("\n", "").rstrip(";")
        compiled_javascript = re.search("return (.+)},", compiled_javascript).group(1)
        if debug:
            print("JS: ", compiled_javascript)

        # Получаем результат выполнения скомпилированного js кода
        # Для этого потребуется js-библиотека z9:
        f = open("../../z9.js")
        z9 = "".join(f.readlines())
        f.close()

        executed_javascript = self.executeJavascript(z9, compiled_javascript, data)
        executed_javascript = filterForExecuted(
            executed_javascript
        ) if filterForExecuted is not None else executed_javascript

        # Основная проверка результатов выполнения
        expected = filterForExecuted(expected) if filterForExecuted is not None else expected
        self.assertEqual(expected, executed_python)
        self.assertEqual(expected, executed_javascript)

    def executeJavascript(self, z9source, compiled, data):
        f = open("current.js", "w+")
        f.writelines(
            '''%s(%s)''' % (
                '''(function(data) {%s print(%s);})''' % (z9source, compiled),
                json.dumps(data, default=json_dumps_handler)
            )
        )
        f.close()

        sp = subprocess.Popen('''java RunScriptDemo 'current.js' ''', shell=True, stdout=subprocess.PIPE)
        res = ""
        s = True
        while s:
            s = sp.stdout.readline()
            res += s.decode('utf-8')
        sp.stdout.close()
        return res

    ################ Фильтры для унификации ответов при разнице, которой можно пренебречь ###########

    def titleCase(self, m):
        """
        Приводит строку к titleCase

        :param m:
        :return:
        """
        return m.capitalize()

    def unifyNone(self, m):
        """
        Заменяем обозначение null в строке на SuitNone()
        :param m:
        :return:
        """
        m = m.replace("null", "SuitNone()")
        return m

    ############################### Общие методы ##################################
    def test_parseFirstLine(self):
        """
        Проверим метод получения первой строки тега (открывающий тег со всеми параметрами)
        """
        tag = XmlTag('''<tagName></tagName>''')
        self.assertEqual("<tagName>", tag.firstLine)

        tag = XmlTag('''<tagName src="somedata"></tagName>''')
        self.assertEqual('''<tagName src="somedata">''', tag.firstLine)

        tag = XmlTag('''<tagName src='somedata' id=222 class="test"></tagName>''')
        self.assertEqual('''<tagName src='somedata' id=222 class="test">''', tag.firstLine)

        tag = XmlTag('''<tagName src='somedata' <tag2 id="222">content</tag2>>tagNameContent</tagName>''')
        self.assertEqual('''<tagName src='somedata' <tag2 id="222">content</tag2>>''', tag.firstLine)

        tag = XmlTag('''<tagName
        class='<tag2 id="222">content</tag2>'>tagNameContent</tagName>''')
        self.assertEqual('''<tagName class='<tag2 id="222">content</tag2>'>''', tag.firstLine)

    def test_getAttribute(self):
        """
        Проверим метод получения значений аттрибутов
        """
        tag = XmlTag('''<tagName
                            src='somedata' empty="" id="222" condition="1 > 2" class="test"
                            name="<anotherTag><p>anotherTagContent</p></anotherTag>">
                            <p>content</p>
                        </tagName>''')
        self.assertEqual("somedata", tag.get("src"))
        self.assertEqual("222", tag.get("id"))
        self.assertEqual("test", tag.get("class"))
        self.assertEqual("<anotherTag><p>anotherTagContent</p></anotherTag>", tag.get("name"))
        self.assertEqual("", tag.get("empty"))
        self.assertEqual(None, tag.get("something"))
        self.assertEqual("1 > 2", tag.get("condition"))

    def test_parseBody(self):
        """ Проверим метод получения тела тега """
        tag = XmlTag('''<tagName class='test'>content</tagName>''')
        self.assertEqual("content", tag.body)

        tag = XmlTag('''<tagName
                        class='test' name="<anotherTag><p>anotherTagContent</p></anotherTag>">
                            <p>content</p><p>content</p>
                        </tagName>''')
        self.assertEqual("<p>content</p><p>content</p>", tag.body)

    def test_spaceTrimmer(self):
        """
        Проверим, что множественные пробелы или табуляция заменяются на один пробел

        """
        template = '''
            Hello world!
            This is a linebreak     and this is multiple spaces     '''
        self.simulate(template, "Hello world! This is a linebreak and this is multiple spaces")

    def test_comments(self):
        """
        Проверим, что комментарии внутри шаблона будут вырезаться из итогового шаблона

        """
        template = '''
            FirstLine
            <!-- Основной контент карточки -->
            SecondLine
        '''
        self.simulate(template, "FirstLine SecondLine")

    ############################################# Переменные #########################################################

    def test_stringify(self):
        """
        Проверим как будут печататься списки и словари

        """
        self.simulate("<var>a</var>", '''[1, 2, 3]''', {"a": [1, 2, 3]}, None, lambda m: m.replace(" ", ""))
        self.simulate("<var>a</var>", '''{"y": "aaa", "x": 1}''', {"a": {"y": "aaa", "x": 1}},
                      filterForExecuted=lambda m: m.replace(" ", ""))
        self.simulate("<var>a</var>", '''[1,null,3,"",false,"True"]''', {"a": [1, None, 3, "", False, "True"]},
                      filterForExecuted=lambda m: m.replace(" ", ""))

    def test_safevaraccess(self):
        """
        Проверим простой вывод значения переменной

        """
        self.simulate("<var>a</var>", "222", {"a": "222"})
        self.simulate("<var>a</var>", "SuitNone()", {"b": "222"}, filterForExecuted=self.unifyNone)
        self.simulate("<var>a</var>", "SuitNone()", {"a": None, "b": "222"}, filterForExecuted=self.unifyNone)

    def test_safevaraccess_default(self):
        """
        Простой вывод значения переменной с указанным значением по умолчанию

        :return:
        """
        self.simulate("<var d='hello'>a</var>", "222", {"a": "222"})
        self.simulate("<var d='hello'>a</var>", "hello", {"b": "222"})
        self.simulate("<var d=''>a</var>", "", {"b": "222"})

    def test_safevaraccess_deep(self):
        """
        Вывод значения переменной из n-вложенности объектов

        :return:
        """
        data = {"classRoom": {"student": {"studentName": "Ivan"}}}
        self.simulate("<var>classRoom.student.studentName</var>", "Ivan", data)
        self.simulate("<var>classRoom.person.studentName</var>", "SuitNone()", data, filterForExecuted=self.unifyNone)
        self.simulate("<var d='Vladimir'>classRoom.person.studentName</var>", "Vladimir", data)

    def test_listPointers(self):
        """
        Проверим синтаксис обращения к элементам списков
        По задумке он не очень то и нужен программисту при итерации по объекту, но нужен самому шаблонизитору.
        Плюс может быть полезен для извлечения нужного элемента из небольших одномерных коллекций (list, tuple, set)

        """
        data = {"classRoom": {"students": [
            {"studentName": "Ivan"},
            {"studentName": "Vladimir"},
        ]}}
        self.simulate("<var>classRoom.students[0].studentName</var>", "Ivan", data)
        self.simulate("<var>classRoom.students[1].studentName</var>", "Vladimir", data)
        self.simulate("<var>classRoom.students[111].studentName</var>", "SuitNone()", data,
                      filterForExecuted=self.unifyNone)
        self.simulate("<var>classRoom.peoples[0].studentName</var>", "SuitNone()", data,
                      filterForExecuted=self.unifyNone)
        self.simulate("<var d='default'>classRoom.peoples[0].studentName</var>", "default", data)

        self.simulate("<var>classRoom.students[0]</var>", '''{"studentName": "Ivan"}''', data,
                      filterForExecuted=lambda m: m.replace(" ", ""))

    def test_comparisons_with_undefined_vars(self):
        """
        Проверим методы сравнения и другие операции с участием неизвестных переменных в условиях

        """
        template = '''
            <if>
                <condition>%s</condition>
                <true>Да</true>
                <false>Нет</false>
            </if>
        '''

        def _cmp(condition, expected):
            self.simulate(template % condition, expected, {"x": 1})

        _cmp("<var>a</var> > 1", "Нет")
        _cmp("<var>a</var> >= 1", "Нет")
        _cmp("<var>a</var> < 1", "Да")
        _cmp("<var>a</var> <= 1", "Да")
        _cmp("<var>a</var> == 1", "Нет")
        _cmp("<var>a</var> != 1", "Да")

        _cmp("<var>a</var> > 0", "Нет")
        _cmp("<var>a</var> >= 0", "Да")
        _cmp("<var>a</var> < 0", "Нет")
        _cmp("<var>a</var> <= 0", "Да")
        _cmp("<var>a</var> == 0", "Нет")
        _cmp("<var>a</var> != 0", "Да")

        _cmp("<var>a</var> > -1", "Да")
        _cmp("<var>a</var> >= -1", "Да")
        _cmp("<var>a</var> < -1", "Нет")
        _cmp("<var>a</var> <= -1", "Нет")
        _cmp("<var>a</var> == -1", "Нет")
        _cmp("<var>a</var> != -1", "Да")

    def test_var_as_default_parameter(self):
        """
        Проверим можем ли мы использовать одну переменную в качестве дефолтного значения для другой
        """
        self.simulate('''<var d="<var>c</var>">a</var>''', "1", {"c": 1, "d": 2})
        #self.simulate('''<var d="<if condition='1 > 0'><var>c</var></if>">a</var>''', "1", {"c": 1, "d": 2})

    #################################### Filters ###################################
    def test_filter_length(self):
        """
        Фильтр length:
        Вычисляет длинну переменной (строки, списка, словаря)

        """

        template = "<var filter='length'>someString</var>"
        self.simulate(template, "8", {"someString": "someText"})
        self.simulate(template, "0", {"someString": None})
        self.simulate(template, "0", {"otherString": "2222"})
        self.simulate(template, "4", {"someString": "2222"})
        self.simulate(template, "3", {"someString": 142})

        data = {"city": {"store": "", "school": {"student": {"Name": "Ivan"}}}}
        # Несуществующие переменные:
        self.simulate('''<var>city.school.student.studentName</var>''', "SuitNone()", data,
                      filterForExecuted=self.unifyNone)
        self.simulate('''<var filter="length">city.school.student.studentName</var>''', "0", data)

    def test_filter_startswith(self):
        """
        Фильтр startswith:
        Проверяет начинается ли значение переменной с определенной подстроки

        """
        self.simulate(
            "<var filter='startswith' startswith-data='При'>a</var>", "True",
            {"a": "Привет"}, None, filterForExecuted=self.titleCase
        )

        self.simulate(
            "<var filter='startswith' startswith-data='При'>a</var>", "False",
            {"a": "Hello!"}, None, filterForExecuted=self.titleCase
        )

        # Проверим значение фильтра внутри условия
        template = '''
            <if condition="<var filter='startswith' startswith-data='При'>a</var>">
                <true>Да!</true>
                <false>Нет!</false>
            </if>
        '''
        self.simulate(template, "Да!", {"a": "Привет"})
        self.simulate(template, "Нет!", {"a": "Hello"})

        # Тоже самое, но используем переменную внутри фильтра
        template = '''
            <if condition="<var filter='startswith' startswith-data='<var>prefix</var>'>a</var>">
                <true>Да!</true>
                <false>Нет!</false>
            </if>
        '''
        self.simulate(template, "Да!", {"a": "Привет", "prefix": "При"})
        self.simulate(template, "Нет!", {"a": "Hello", "prefix": "При"})

        # Не существующие переменные
        self.simulate(
            '''<var filter="startswith" startswith-data="<var>a</var>">b</var>''', 'False', {}, None, self.titleCase
        )
        self.simulate(
            '''<var filter="startswith" startswith-data="<var>a</var>">b</var>''',
            'False', {"b": "Привет"}, None, self.titleCase
        )
        self.simulate(
            '''<var filter="startswith" startswith-data="<var>a</var>">b</var>''',
            'False', {"a": "При"}, None, self.titleCase
        )

    def test_filter_in(self):
        """
        Фильтр in:
        Проверят входит ли указанная переменная в указанный массив или объект

        """
        self.simulate(
            '<var filter="in" in-data="<var>haystack</var>">needle</var>', "True",
            {"needle": "222", "haystack": ["qasa", "222"]}, name=None, filterForExecuted=self.titleCase
        )

        # Проверим значение фильтра внутри условия
        template = '''
            <if condition="<var filter='in' in-data='<var>haystack</var>'>needle</var>">
                <true>Да!</true>
                <false>Нет!</false>
            </if>
        '''
        self.simulate(template, "Да!", {"needle": "222", "haystack": ["111", "222"]})
        self.simulate(template, "Нет!", {"needle": "222", "haystack": ["111", "333"]})
        self.simulate(template, "Да!", {"needle": "222", "haystack": {"222": "yes"}})
        self.simulate(template, "Нет!", {"needle": "222", "haystack": {"111": "yes"}})
        self.simulate(template, "Да!", {"needle": "s", "haystack": "sdgff"})
        self.simulate(template, "Нет!", {"needle": "s", "haystack": "_dgff"})

        # Отсутствующие переменные
        self.simulate(template, "Нет!", {})
        self.simulate(template, "Нет!", {"needle": "222"})
        self.simulate(template, "Нет!", {"haystack": ["222"]})

    def test_filter_in_inline(self):
        """
        Проверим фильтр in, если в качестве списка будет использована json-строка

        """
        template = '''
        <if>
            <condition><var filter='in' in-data='["Y", " "]'>propertyName</var></condition>
            <true>Да</true>
            <false>Нет</false>
        </if>
        '''
        self.simulate(template, "Да", {"propertyName": "Y"})
        self.simulate(template, "Да", {"propertyName": " "})
        self.simulate(template, "Нет", {"propertyName": "qwerty"})

    def test_filter_notin(self):
        """
        Фильтр notin:
        Проверяет не входит ли переменная в указанный список.
        Работает аналогично фильтру in

        """
        template = '''
        <if>
            <condition><var filter='notin' notin-data='["Y", " "]'>propertyName</var></condition>
            <true>Да</true>
            <false>Нет</false>
        </if>
        '''
        self.simulate(template, "Нет", {"propertyName": "Y"})
        self.simulate(template, "Нет", {"propertyName": " "})
        self.simulate(template, "Да", {"propertyName": "qwerty"})

    def test_filter_contains(self):
        """
        Фильтр contains:
        Проверяет содержит ли некая переменная указанное значение

        """
        template = '''
        <if>
            <condition><var filter='contains' contains-data='AAA'>propertyName</var></condition>
            <true>Да</true>
            <false>Нет</false>
        </if>
        '''
        self.simulate(template, "Да",   {"propertyName": "cccAAAmmm"})
        self.simulate(template, "Да",   {"propertyName": "AAAmmm"})
        self.simulate(template, "Нет",  {"propertyName": "cccBBBmmm"})
        self.simulate(template, "Нет",  {"propertyName": "cccaaammm"})
        self.simulate(template, "Нет",  {"propertyName": "cccAAmAmm"})
        self.simulate(template, "Да",   {"propertyName": ["AAA", "BBB", 222]})
        self.simulate(template, "Нет",  {"propertyName": [111, "BBB", 222]})
        self.simulate(template, "Нет",  {"propertyName": [111, "aaa", 222]})
        self.simulate(template, "Да",   {"propertyName": {"AAA": 111, "BBB": 222}})
        self.simulate(template, "Нет",  {"propertyName": {"CCC": 111, "BBB": 222}})

    def test_filter_dateformat(self):
        """
        Проверим фильтр для преобразования даты и времени

        """
        from datetime import datetime, date, time
        self.simulate(
            "<var filter='dateformat' dateformat-data='%d.%m.%y'>date</var>", "04.10.13", {"date": date(2013, 10, 4)}
        )
        self.simulate(
            "<var filter='dateformat' dateformat-data='%H:%M:%S'>date</var>", "07:05:08", {"date": time(7, 5, 8)}
        )
        self.simulate(
            "<var filter='dateformat' dateformat-data='%d-%m-%y %H:%M:%S'>date</var>", "08-09-07 07:05:08",
            {"date": datetime(2007, 9, 8, 7, 5, 8)}
        )

    # # # ################################ Conditions ###################################

    def test_сonditions(self):
        """
        Простое условие, развернутый синтакис

        """
        template = '''
            <if>
                <condition>1 > 2</condition>
                <true>yes</true>
                <false>no</false>
            </if>
        '''
        self.simulate(template, "no")

    def test_сonditionsWithVariable(self):
        """
        Условие, в результирующих объектах вставлены переменные шаблона

        """
        template = '''
            <if>
                <condition>1 > 2</condition>
                <true><var>a</var></true>
                <false><var>b</var></false>
            </if>
        '''
        data = {"a": 1, "b": 2}
        self.simulate(template, "2", data)

    def test_сonditionsShortSyntax(self):
        """
        Укороченный синтаксис для оператора условий
        Указываем только значение для положительного результата проверки

        """
        template = '''
            <if>
                <condition>1 > 2</condition>
                <true>aaa</true>
            </if>
        '''
        self.simulate(template, "")

    def test_сonditionsAttrShortSyntax(self):
        """
        Укороченный синтаксис для оператора условий
        Указываем только значение для положительного результата проверки
        Само условие пишем в аттрибут тега if

        """
        template = '''<if condition="1 > 2">aaa</if>'''
        self.simulate(template, "")

        template = '''<if condition="1 < 2">aaa</if>'''
        self.simulate(template, "aaa")

    def test_conditionInAttribute(self):
        """
        Проверим возможность использования условной логики внутри тегов

        """
        template = '''
            <meta name="description" content="
            <if>
                <condition><var filter='length'>a</var> > 0</condition>
                <true><var>a</var></true>
                <false><var>b</var></false>
            </if>" />
        '''
        self.simulate(template, '''<meta name="description" content="hello" />''', {"a": "", "b": "hello"})
        self.simulate(template, '''<meta name="description" content="hi" />''', {"a": "hi", "b": "hello"})

    def test_condition_cmp_with_boolean(self):
        """
        Проверим сравнение переменной с булевым значением
        Сложность в том, что для разных языков есть существенная разница между false и False

        """
        template = '''
            <if>
            <condition><var filter="bool">a</var> == true</condition>
            <true>Да</true>
            <false>Нет</false>
            </if>
        '''
        self.simulate(template, "Да", {"a": True})
        self.simulate(template, "Да", {"a": "1"})
        self.simulate(template, "Нет", {"a": False})
        self.simulate(template, "Нет", {"b": True})

    def test_logical_operators(self):
        """
        Проверим методы объединения и пересечения условий

        """
        template = '''
        <if>
        <condition><var filter="bool">isOk</var> && <var>value</var> == 2</condition>
        <true>Да</true>
        <false>Нет</false>
        </if>
        '''
        self.simulate(template, "Да", {"isOk": True, "value": 2})
        self.simulate(template, "Да", {"isOk": "Yo", "value": 2})
        self.simulate(template, "Нет", {"isOk": True, "value": 3})
        self.simulate(template, "Нет", {"isOk": "Yo", "value": 3})
        self.simulate(template, "Нет", {"isOk": False, "value": 2})
        self.simulate(template, "Нет", {"isOk": "False", "value": 2})
        self.simulate(template, "Нет", {"value": 2})
        self.simulate(template, "Нет", {})

        template = '''
        <if>
        <condition><var filter="bool">isOk</var> || <var filter="int">value</var> == 2</condition>
        <true>Да</true>
        <false>Нет</false>
        </if>
        '''
        self.simulate(template, "Да", {"isOk": True, "value": 2})
        self.simulate(template, "Да", {"isOk": "Yo", "value": 2})
        self.simulate(template, "Да", {"isOk": True, "value": 3})
        self.simulate(template, "Да", {"isOk": "Yo", "value": 3})
        self.simulate(template, "Да", {"isOk": False, "value": 2})
        self.simulate(template, "Да", {"isOk": "False", "value": 2})
        self.simulate(template, "Да", {"value": 2})
        self.simulate(template, "Нет", {"isOk": "False", "value": 3})
        self.simulate(template, "Нет", {"isOk": False, "value": 3})
        self.simulate(template, "Нет", {"isOk": None, "value": 3})
        self.simulate(template, "Нет", {})

    # #################################### Lists ###################################

    def test_list(self):
        """
        Простой список.

        Для итерируемого объекта в аттрибуте 'in'
        указывается имя локальной перемнной (аттрибут 'for'),
        которая будет доступна в цикле
        Шаблон элемента списка передается внунтри тега list

        """
        template = '''
            <list for="a" in="<var>numbers</var>">
                <p><var>a</var></p>
            </list>
        '''
        data = {"numbers": [1, 2, 3]}
        self.simulate(template, "<p>1</p><p>2</p><p>3</p>", data)

    def test_listWithConditions(self):
        """
        Список. Но для каждой итерации
        шаблон выбирается в соответствии с условием

        """
        template = '''
            <list for="num" in="<var>numbers</var>">
                <if>
                    <condition><var>num</var> == 2</condition>
                    <true><p>!<var>num</var>!</p></true>
                    <false><p><var>num</var></p></false>
                </if>
            </list>
        '''
        data = {"numbers": [1, 2, 3]}
        self.simulate(template, "<p>1</p><p>!2!</p><p>3</p>", data)

    def test_listWithDoubleConditions(self):
        """
        Список с условиями двойной вложенности.
        Должно имитировать комплексное сложное взаимное использование тегов.

        """
        template = '''
            <list for="num" in="numbers">
                <if>
                    <condition><var>num</var> == 2</condition>
                    <true>
                        <if>
                            <condition><var>num</var> == 1</condition>
                            <true>111</true>
                            <false>222</false>
                        </if>
                    </true>
                    <false><p><var>num</var></p></false>
                </if>
            </list>
        '''
        data = {"numbers": [1, 2, 3]}
        self.simulate(template, "<p>1</p>222<p>3</p>", data)

    def test_listWithConditionsSurroundedBySomeText(self):
        """
        Список, где шаблон элемента списка - это условие, обрмаленное обычным текстом
        Заодно проверим использование кавычек  (не должны конфликтовать с системными)

        """
        template = '''
            <list for="num" in="numbers">
                aaa
                <if>
                    <condition><var>num</var> == 2</condition>
                    <true><p class="testquotes" id="sds">!<var>num</var>!</p></true>
                    <false><p><var>num</var></p></false>
                </if>
                bbb
            </list>
        '''
        data = {"numbers": [1, 2, 3]}
        self.simulate(template, '''aaa<p>1</p>bbbaaa<p class="testquotes" id="sds">!2!</p>bbbaaa<p>3</p>bbb''', data)

    def test_listWithListOfDictionariesAsIter(self):
        """
        В качестве итерируемого объекта можно передавать список словарей (ассоциативный массив объектов),

        """
        template = '''
            <list for="user" in="users">
                <div><var>user.name</var> - <var>user.age</var></div>
            </list>
        '''
        data = {
            "users": [
                {"name": "Andrey", 	"age": 24},
                {"name": "Alex", 	"age": 19},
                {"name": "Anna", 	"age": 31}
            ]
        }
        self.simulate(template, '''<div>Andrey - 24</div><div>Alex - 19</div><div>Anna - 31</div>''', data)

    def test_listWithDictionaryAsIterable(self):
        """
        В качестве итерируемого объекта можно передавать не только список (массив), но и словарь (объект)
        Итерация должна идти по значениям словаря (значениям свойств объекта)

        """
        template = '''
            <list for="property" in="object">
                <div><var>property</var></div>
            </list>
        '''
        data = {"object": {"prop1": 1, "prop2": 2, "prop3": 3}}
        self.simulate(template, '''<div>1</div><div>2</div><div>3</div>''', data, None,
                      lambda m: m.replace("1", "@").replace("2", "@").replace("3", "@"))

    def test_listWithDictionaryAsIterableKeyAndValue(self):
        """
        Итерация может идти по ключам словаря и по его значениям

        """
        template = '''
            <list for="prop,value" in="object">
                <div><var>prop</var> - <var>value</var></div>
            </list>
        '''
        data = {"object": {"prop1": 1, "prop2": 2, "prop3": 3}}
        self.simulate(template, '''<div>prop1 - 1</div><div>prop2 - 2</div><div>prop3 - 3</div>''', data, None,
                      lambda m: m.replace("1", "@").replace("2", "@").replace("3", "@"))

    def test_arrayAccessToIterVar(self):
        """
        Если переменная цикла является массивом, то должна быть возможность обращаться к его элементам по индексу

        """
        template = '''
            <var>listOfArrays[0][1].name</var>
            <list for="array" in="listOfArrays">
                <div><var>array[0]</var> - <var>array[1].name</var></div>
            </list>
        '''
        data = {
            "listOfArrays": [
                ["Первый", {"name": "Шелдон"}],
                ["Второй", {"name": "Леонард"}]
            ]
        }
        self.simulate(template, '''Шелдон<div>Первый - Шелдон</div><div>Второй - Леонард</div>''', data)

    def test_doubleNestedList(self):
        """
        Проверка вложенных циклов

        """
        template = '''
            <list for="country" in="places">
                <var>country.CountryName</var>
                <list for="region" in="country.Regions">
                    <var>region.RegionName</var>
                </list>
            </list>
        '''
        data = {
            "places": [
                {
                    "CountryName": "Russia", "Regions": [
                        {"RegionName": "Москва"},
                        {"RegionName": "Спб"}
                    ]
                }
            ]
        }

        expected = '''RussiaМоскваСпб'''
        self.simulate(template, expected, data)

    def test_iterationCounter(self):
        """
        Получение номера текущей итерации

        """
        template = '''
            <list for="item" in="items">
                <if>
                    <condition><var>i</var> == 1</condition>
                    <true><var>item</var> - Первый!</true>
                    <false><var>item</var></false>
                </if>
            </list>
        '''
        template2 = '''
            <list for="item" in="items">
                <if>
                    <condition><var>i</var> == <var filter="length">items</var></condition>
                    <true><var>item</var> - Последний!</true>
                    <false><var>item</var></false>
                </if>
            </list>
        '''
        self.simulate(template, "1 - Первый!234", {"items": [1, 2, 3, 4]})
        self.simulate(template2, "1234 - Последний!", {"items": [1, 2, 3, 4]})

    #################################### Expressions ###################################

    def test_expression(self):
        """
        Шаблонизатор поддерживает выполнение простейших арифметических операций

        """
        self.simulate("<expression>1 + 3</expression>", "4")
        self.simulate("<expression>1 + <var>someVar</var></expression>", "4", {"someVar": "3"})

    #################################### Embedded CSS ###################################
    def test_embeddedCSS(self):
        """
        Проверим возможность внедрения стилей CSS в шаблон

        """
        template = '''
        <div id="target">some content</div>
        <style>
            #target { background-color: red; }
        </style>
        '''

        # Запишем шаблон в файл
        self.assertFalse(os.path.isfile("views/subfolder/template7.html"))
        f = open("views/subfolder/template7.html", "w+")
        f.writelines(template)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template7.html"))

        self.assertFalse(os.path.isfile("views/__css__/subfolder_template7.css"))

        os.chdir("views")
        self.c.compile()
        os.chdir("../")

        # Сам шаблон не должен содержать стилей
        self.assertEqual(
            '''<div id="target">some content</div>''',
            Suit("subfolder.template7").execute()
        )

        # Проверим наличие файла css и его содержимое
        self.assertTrue(os.path.isfile("views/__css__/subfolder_template7.css"))
        f = open("views/__css__/subfolder_template7.css")
        css_written = "".join(f.readlines())
        f.close()
        self.assertEqual('''#target { background-color: red; }''', trimSpaces(css_written))

    def test_embeddedJS(self):
        """
        Проверим возможность внедрения js-сценариев непосредственно в шаблон

        """
        template = '''
        <div id="target">some content</div>
        <script src="something"></script>
        <script>
        (function() {
            return {
                sayHello: function() { alert("Hello"); }
            }
        })
        </script>
        '''

        # Запишем шаблон в файл
        self.assertFalse(os.path.isfile("views/subfolder/template8.html"))
        f = open("views/subfolder/template8.html", "w+")
        f.writelines(template)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template8.html"))

        self.assertFalse(os.path.isfile("views/__js__/subfolder_template8.js"))

        os.chdir("views")
        self.c.compile()
        os.chdir("../")

        # Сам шаблон не должен содержать js (за исключением подключаемых сценариев)
        self.assertEqual(
            trimSpaces('''
            <div id="target">some content</div>
            <script src="something"></script>
            '''),
            trimSpaces(Suit("subfolder.template8").execute())
        )

        # Проверим наличие файла jss и его содержимое
        # Он должен содержать не только сам шаблон, но и доп. функцию
        self.assertTrue(os.path.isfile("views/__js__/subfolder_template8.js"))
        f = open("views/__js__/subfolder_template8.js")
        js_written = "".join(f.readlines())
        f.close()
        expected = '''
            z9.SuitApi.addTemplate("subfolder.template8", function(data) {
                if (data == null) { data = {}; };
                return "<div id=\\"target\\">some content</div><script src=\\"something\\"></script>"
            }, function() {
                return (function() {
                    return {
                        sayHello: function() { alert("Hello"); }
                    }
                })()
            });
        '''
        self.assertEqual(trimSpaces(expected), trimSpaces(js_written))
        #self.assertEqual(expected, js_written)

    #################################### Include & Rebase ###################################

    def test_breakPoint_include(self):
        """
        Сделаем простое включение одного шаблона в другой

        """
        template = '''1<breakpoint include="subfolder.template20"></breakpoint>3'''
        template2 = '''-<var>a</var>-'''
        dataForTemplate2 = {"a": 2}

        expected1 = '''1-2-3'''
        expected2 = '''-2-'''

        # Запишем оба шаблона в файлы
        self.assertFalse(os.path.isfile("views/subfolder/template10.html"))
        f = open("views/subfolder/template10.html", "w+")
        f.writelines(template)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template10.html"))

        self.assertFalse(os.path.isfile("views/subfolder/template20.html"))
        f = open("views/subfolder/template20.html", "w+")
        f.writelines(template2)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template20.html"))

        # И скомпилируем их
        os.chdir("views")
        self.c.compile()
        os.chdir("../")

        # Проверим второй шаблон (особого интереса не представляет)
        executed2 = Suit("subfolder.template20").execute(dataForTemplate2)
        self.assertEqual(expected2, executed2)

        # Проверим первый шаблон
        executed1 = Suit("subfolder.template10").execute(dataForTemplate2)
        self.assertEqual(expected1, executed1)

    def test_breakpoint_include_in_list(self):
        """
        Проверим включение подшаблона внутри цикла. Включаемый шаблон должен видеть переменные цикла, как свои

        """
        templateList = '''
            <list for="item" in="items">
                <breakpoint include="subfolder.line"></breakpoint>
            </list>
        '''
        templateLine = '''<var>item.a</var><style>css here</style>'''
        items = [{"a": 1}, {"a": 2}, {"a": 3}]

        self.simulate(templateLine, "2", {"item": {"a": 2}}, "line")
        self.simulate(templateList, "123", {"items": items}, "list")

    def test_breakpoint_rebase(self):
        """
        Сделаем простое наследование

        """
        template3 = '''
            1<breakpoint name="PlaceToOverride">ContentInBaseTemplate<var>a</var></breakpoint>3
            <breakpoint name="PlaceToBeKeptAsIs">SHOULD STAY AFTER REBASE</breakpoint>
        '''
        template4 = '''
            <rebase>subfolder.template3</rebase>
            <breakpoint name="PlaceToOverride">ContentInChildTemplate<var>b</var></breakpoint>
            <breakpoint name="PlaceToDisapear">SHOULD DISAPEARED</breakpoint>
        '''
        dataForTemplate3 = {"a": "@"}
        dataForTemplate4 = {"b": "#"}
        expected3 = '''1ContentInBaseTemplate@3SHOULD STAY AFTER REBASE'''
        expected4 = '''1ContentInChildTemplate#3SHOULD STAY AFTER REBASE'''

        self.simulate(template3, expected3, dataForTemplate3, "template3")
        self.simulate(template4, expected4, dataForTemplate4)

    def test_breakpoint_rebase_multiline(self):
        """
        Должно поддерживаться наследование по цепочке 1->2->3...->n

        """
        template1 = '''1-<breakpoint name="first">0-0-0-0-0-0-0-0</breakpoint>-10'''
        template2 = '''
            <rebase>subfolder.baseTemplate</rebase>
            <breakpoint name="first">
                2-<breakpoint name="second">0-0</breakpoint>-5-6-<breakpoint name="third">0-0</breakpoint>-9
            </breakpoint>
        '''
        template3 = '''
            <rebase>subfolder.firstTemplate</rebase>
            <breakpoint name="second">3-4</breakpoint>
            '''
        template4 = '''
            <rebase>subfolder.secondTemplate</rebase>
            <breakpoint name="third">7-8</breakpoint>
        '''

        self.simulate(template1, '''1-0-0-0-0-0-0-0-0-10''', None, "baseTemplate")
        self.simulate(template2, '''1-2-0-0-5-6-0-0-9-10''', None, "firstTemplate")
        self.simulate(template3, '''1-2-3-4-5-6-0-0-9-10''', None, "secondTemplate")
        self.simulate(template4, '''1-2-3-4-5-6-7-8-9-10''', None, "lastTemplate")

    def test_breakpoint_rebase_and_include(self):
        """
        Должно работать
        """
        templateMain = '''1-<breakpoint name="center">5</breakpoint>-10'''
        self.simulate(templateMain, '''1-5-10''', None, "mainTemplate")

        templateIncl = "<if><condition> 1 == 1</condition><true>3</true></if>"
        self.simulate(templateIncl, "3", None, "replacement")

        templateResult = '''
        <rebase>subfolder.mainTemplate</rebase>
        <breakpoint name="center">
            <if><condition>2 == 2</condition><true>3</true></if>
            <breakpoint include="subfolder.replacement"></breakpoint>
        </breakpoint>
        '''
        self.simulate(templateResult, "1-33-10")

    def test_breakpoint_rebase_with_script(self):
        """
        Если в шаблоне наследнике определены свои js-скрипты, то они должны быть ядром шаблона, а не скрипты родителя
        """
        templateMain = '''
            <div>main</div>
            <script>
                (function() {
                    return {
                        sayHello: function() { alert("Hello"); }
                    }
                })
            </script>
        '''
        self.simulate(templateMain, '''<div>main</div>''', None, "mainTemplate2")
        self.assertTrue(os.path.isfile("views/__js__/subfolder_mainTemplate2.js"))
        f = open("views/__js__/subfolder_mainTemplate2.js")
        js_written = "".join(f.readlines())
        f.close()
        expected = '''
            z9.SuitApi.addTemplate("subfolder.mainTemplate2", function(data) {
                if (data == null) { data = {}; };
                return "<div>main</div>"
            }, function() {
                return (function() {
                    return {
                        sayHello: function() { alert("Hello"); }
                    }
                })()
            });
        '''
        self.assertEqual(trimSpaces(expected), trimSpaces(js_written))

        templateChild = '''
            <rebase>subfolder.mainTemplate2</rebase>
            <div>child</div>
            <script>
                (function() {
                    return {
                        sayHello: function() { alert("Hello from child template"); }
                    }
                })
            </script>
        '''
        self.simulate(templateChild, "<div>main</div>", None, "templateChild")
        self.assertTrue(os.path.isfile("views/__js__/subfolder_templateChild.js"))
        f = open("views/__js__/subfolder_templateChild.js")
        js_written = "".join(f.readlines())
        f.close()
        expected = '''
            z9.SuitApi.addTemplate("subfolder.templateChild", function(data) {
                if (data == null) { data = {}; };
                return "<div>main</div>"
            }, function() {
                return (function() {
                    return {
                        sayHello: function() { alert("Hello from child template"); }
                    }
                })()
            });
        '''
        self.assertEqual(trimSpaces(expected), trimSpaces(js_written))

    # ################################# Регрессионные тесты альфа-тестирования ##################################

    def test_regressive_specialChars(self):
        """
        Регрессионный тест:
        Проверяем корректно ли шаблонизатор справляется со спец.символами
        В частности, компилятор не работает, если внутри него обнаружится знак процента (%)
        Проблема временно решается путем экранирования этого знака следующим способом - %% = %

        """
        self.simulate('''100%;<var>a</var>''', "100%;OK", {"a": "OK"})
        self.simulate('''100%;''', "100%;")

    def test_regressive_var_with_filter_in_condition_in_list(self):
        """
        Переменные цикла странно обрабатывались при использовании фильтров

        """
        template = '''
            <list for="item" in="items">
                <if condition="<var filter='length'>item</var> > 0">
                    <div><var>item</var></div>
                </if>
            </list>
        '''

        expected = trimSpaces('''
            <div>a</div><div>b</div><div>c</div>
        ''')
        self.simulate(template, expected, {"items": ["a", "b", "", "c"]})

    def test_regressive_nested_list_with_iterable_dict(self):
        """
        Если запустить итерацию по ключам и значениям словаря, а значением словаря будет выступать список,
        по которому тоже нужно итерироваться, то второй цикл итерации почему-то не запускается

        """
        data = {1: ["a", "b", "c"], 2: ["A", "B", "C"]}
        template = '''
            <list for="num,letters" in="data">
                (<var>num</var>)
                <list for="char" in="letters">
                    <var>num</var><var>char</var>
                </list>
            </list>
        '''
        self.simulate(template, "(1)1a1b1c(2)2A2B2C", {"data": data})

    def test_decorator(self):
        """
        Протестируем использование декоратора

        """
        template = '''
            <var>a.one</var> != <var>a.two</var>
        '''
        data = {"a": {"one": 1, "two": 2}}
        self.assertFalse(os.path.isfile("views/subfolder/decoratedTemplte.html"))
        f = open("views/subfolder/decoratedTemplte.html", "w+")
        f.writelines(template)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/decoratedTemplte.html"))
        os.chdir("views")
        self.c.compile()
        os.chdir("../")
        self.assertEqual("1 != 2", Suit("subfolder.decoratedTemplte").execute(data))

        # Проверим декоратор с параметром
        @suit("subfolder.decoratedTemplte")
        def getTemplateWithArgs(valueForOne):
            """
            Функция, которая должна вернуться словарь с данными для использования шаблонизатором
            :param valueForOne: Один из параметров, передается ей напрямую

            """
            return {"a": {"one": valueForOne, "two": 2}}

        self.assertEqual("1 != 2", getTemplateWithArgs(1))

    ########################################### Compiler tests ###################################################

    def test_compiler(self):
        """
        Тестируем уровень работы с файлами

        """
        template = '''0<var>a</var>2'''
        data = {"a": 1}
        expected = "012"

        # Запишем шаблон в файл
        self.assertFalse(os.path.isfile("views/myFirstTemplate.html"))
        f = open("views/myFirstTemplate.html", "w+")
        f.writelines(template)
        f.close()
        self.assertTrue(os.path.isfile("views/myFirstTemplate.html"))

        # Скомпилируем его в исходный код на python, а также соберем библиотеки css и js
        self.assertFalse(os.path.isfile("views/__py__/myFirstTemplate.py"))
        self.assertFalse(os.path.isfile("views/__js__/myFirstTemplate.js"))
        self.assertFalse(os.path.isfile("views/__css__/myFirstTemplate.css"))
        self.assertFalse(os.path.isfile("views/__py__/__init__.py"))
        os.chdir("views")
        self.c.compile()
        os.chdir("../")
        self.assertTrue(os.path.isfile("views/__py__/myFirstTemplate.py"))
        self.assertTrue(os.path.isfile("views/__js__/myFirstTemplate.js"))
        self.assertTrue(os.path.isfile("views/__css__/myFirstTemplate.css"))
        self.assertTrue(os.path.isfile("views/__py__/__init__.py"))
        executed = Suit("myFirstTemplate").execute(data)

        self.assertEqual(expected, executed)

    def test_compiler_path(self):
        """
        Компилятор должен уметь работать не только с именами шаблонов, но и с путями до них
        Чтобы можно было удобно организовать папку views, создав доп. каталоги

        """
        template = '''0<var>a</var>2'''
        data = {"a": 1}
        expected = "012"

        self.assertFalse(os.path.isfile("views/subfolder/template.html"))
        f = open("views/subfolder/template.html", "w+")
        f.writelines(template)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template.html"))

        # Скомпилируем его в исходный код на python и js
        self.assertFalse(os.path.isfile("views/__py__/subfolder_template.py"))
        self.assertFalse(os.path.isfile("views/__js__/subfolder_template.js"))
        os.chdir("views")
        self.c.compile()
        os.chdir("../")
        self.assertTrue(os.path.isfile("views/__py__/subfolder_template.py"))
        self.assertTrue(os.path.isfile("views/__js__/subfolder_template.js"))

        executed = Suit("subfolder.template").execute(data)
        self.assertEqual(expected, executed)

    def test_build_js(self):
        """
        Компилятор должен уметь собирать все скомпилированные js-шаблоны в единый js-файл,
        который было бы удобно подключать к проекту

        """
        # Напишем два шаблона и запишем их в файлы
        template1 = '''0<var>a</var>2'''
        template2 = '''3<var>b</var>5'''

        self.assertFalse(os.path.isfile("views/subfolder/template1.html"))
        f = open("views/subfolder/template1.html", "w+")
        f.writelines(template1)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template1.html"))

        self.assertFalse(os.path.isfile("views/subfolder/template2.html"))
        f = open("views/subfolder/template2.html", "w+")
        f.writelines(template2)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template2.html"))

        self.assertFalse(os.path.isfile("views/__js__/all.subfolder.js"))
        # Соберем в единое целое
        os.chdir("views")
        self.c.compile()
        self.c.build()
        os.chdir("../")
        self.assertTrue(os.path.isfile("views/__js__/all.subfolder.js"))

        # Теперь проверим содержимое собранного файла:
        expected = '''
            z9.SuitApi.addTemplate("subfolder.template1",
            function(data) { if (data == null) { data = {}; };
            return "0{0}2".format(z9.SuitRunTime.stringify(z9.SuitRunTime.var(function(){
            return data["a"]; }, null))) }, null);
            z9.SuitApi.addTemplate("subfolder.template2", function(data) { if (data == null) { data = {}; };
            return "3{0}5".format(z9.SuitRunTime.stringify(z9.SuitRunTime.var(function(){
            return data["b"]; }, null))) }, null);
        '''
        f = open("views/__js__/all.subfolder.js")
        content = "".join(f.readlines())
        f.close()
        self.assertEqual(trimSpaces(expected), trimSpaces(content))

    def test_build_css(self):
        """
        Компилятор должен уметь собирать все css-стили в единый css-файл,
        который было бы удобно подключать к проекту

        """
         # Напишем два шаблона и запишем их в файлы
        template1 = '''0<var>a</var>2<style>html { background-color: red; }</style>'''
        template2 = '''3<var>b</var>5<style>body { background-color: black; }</style>'''

        self.assertFalse(os.path.isfile("views/subfolder/template1.html"))
        f = open("views/subfolder/template1.html", "w+")
        f.writelines(template1)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template1.html"))

        self.assertFalse(os.path.isfile("views/subfolder/template2.html"))
        f = open("views/subfolder/template2.html", "w+")
        f.writelines(template2)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template2.html"))

        self.assertFalse(os.path.isfile("views/__css__/all.subfolder.css"))
        # Соберем в единое целое
        os.chdir("views")
        self.c.compile()
        self.c.build()
        os.chdir("../")
        self.assertTrue(os.path.isfile("views/__css__/all.subfolder.css"))

        # Теперь проверим содержимое собранного файла:
        expected = '''
        body { background-color: black; }html { background-color: red; }
        '''

        f = open("views/__css__/all.subfolder.css")
        content = "".join(f.readlines())
        f.close()
        self.assertEqual(trimSpaces(expected), trimSpaces(content))

    def test_compile_all_and_build_nested_catalogs(self):
        """
        Проверим случай, когда шаблоны размещены во многих каталогах и на разных уровнях вложенности.
        Compile - должен скомпилировать все шаблоны и сложить их в каталог __compiled__
        Build - должен собрать из скомпилированных шаблонов общие билды для каждого отдельного каталога и один ощбий
        билд, содержащий все шаблоны.

        """
        os.mkdir("views/subfolder/subsubfolder1/")
        os.mkdir("views/subfolder/subsubfolder2/")

        # Два шаблона для views/subfolder/subsubfolder1/
        self.assertFalse(os.path.isfile("views/subfolder/subsubfolder1/1.html"))
        f = open("views/subfolder/subsubfolder1/1.html", "w+")
        f.writelines("template_content")
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/subsubfolder1/1.html"))

        self.assertFalse(os.path.isfile("views/subfolder/subsubfolder1/2.html"))
        f = open("views/subfolder/subsubfolder1/2.html", "w+")
        f.writelines("template_content")
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/subsubfolder1/2.html"))

        # Два шаблона для views/subfolder/subsubfolder2/
        self.assertFalse(os.path.isfile("views/subfolder/subsubfolder2/3.html"))
        f = open("views/subfolder/subsubfolder2/3.html", "w+")
        f.writelines("template_content")
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/subsubfolder2/3.html"))

        self.assertFalse(os.path.isfile("views/subfolder/subsubfolder2/4.html"))
        f = open("views/subfolder/subsubfolder2/4.html", "w+")
        f.writelines("template_content")
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/subsubfolder2/4.html"))

        # Один шаблон положим непосредственно в views/subfolder/
        self.assertFalse(os.path.isfile("views/subfolder/5.html"))
        f = open("views/subfolder/5.html", "w+")
        f.writelines("template_content")
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/5.html"))

        # Один шаблон положим непосредственно в views
        self.assertFalse(os.path.isfile("views/6.html"))
        f = open("views/6.html", "w+")
        f.writelines("template_content")
        f.close()
        self.assertTrue(os.path.isfile("views/6.html"))

        # Убедимся, что скомиллированных и собранных файлов еще нет
        # Скомпилированные:
        self.assertFalse(os.path.isfile("views/__py__/subfolder_subsubfolder1_1.py"))
        self.assertFalse(os.path.isfile("views/__js__/subfolder_subsubfolder1_1.js"))
        self.assertFalse(os.path.isfile("views/__py__/subfolder_subsubfolder1_2.py"))
        self.assertFalse(os.path.isfile("views/__js__/subfolder_subsubfolder1_2.js"))
        self.assertFalse(os.path.isfile("views/__py__/subfolder_subsubfolder2_3.py"))
        self.assertFalse(os.path.isfile("views/__js__/subfolder_subsubfolder2_3.js"))
        self.assertFalse(os.path.isfile("views/__py__/subfolder_subsubfolder2_4.py"))
        self.assertFalse(os.path.isfile("views/__js__/subfolder_subsubfolder2_4.js"))

        self.assertFalse(os.path.isfile("views/__py__/subfolder_5.py"))
        self.assertFalse(os.path.isfile("views/__js__/subfolder_5.js"))

        self.assertFalse(os.path.isfile("views/__py__/6.py"))
        self.assertFalse(os.path.isfile("views/__js__/6.js"))

        # Собранные:
        self.assertFalse(os.path.isfile("views/__js__/all.js"))
        self.assertFalse(os.path.isfile("views/__js__/all.subfolder.js"))
        self.assertFalse(os.path.isfile("views/__js__/all.subfolder.subsubfolder1.js"))
        self.assertFalse(os.path.isfile("views/__js__/all.subfolder.subsubfolder2.js"))

        # Зайдем в каталог views, скомпиллируем все шаблоны и
        # соберем все билды, вернемся в обратно в текущий каталог:
        os.chdir("views")
        self.c.compile()
        self.c.build()
        os.chdir("../")

        # Ну а теперь, убедимся, что все ожидаемые файлы созданы и находятся на своих местах:

        self.assertTrue(os.path.isfile("views/__py__/subfolder_subsubfolder1_1.py"))
        self.assertTrue(os.path.isfile("views/__js__/subfolder_subsubfolder1_1.js"))
        self.assertTrue(os.path.isfile("views/__py__/subfolder_subsubfolder1_2.py"))
        self.assertTrue(os.path.isfile("views/__js__/subfolder_subsubfolder1_2.js"))
        self.assertTrue(os.path.isfile("views/__py__/subfolder_subsubfolder2_3.py"))
        self.assertTrue(os.path.isfile("views/__js__/subfolder_subsubfolder2_3.js"))
        self.assertTrue(os.path.isfile("views/__py__/subfolder_subsubfolder2_4.py"))
        self.assertTrue(os.path.isfile("views/__js__/subfolder_subsubfolder2_4.js"))

        self.assertTrue(os.path.isfile("views/__py__/subfolder_5.py"))
        self.assertTrue(os.path.isfile("views/__js__/subfolder_5.js"))

        self.assertTrue(os.path.isfile("views/__py__/6.py"))
        self.assertTrue(os.path.isfile("views/__js__/6.js"))

        # Собранные:
        self.assertTrue(os.path.isfile("views/__js__/all.js"))
        self.assertTrue(os.path.isfile("views/__js__/all.subfolder.js"))
        self.assertTrue(os.path.isfile("views/__js__/all.subfolder.subsubfolder1.js"))
        self.assertTrue(os.path.isfile("views/__js__/all.subfolder.subsubfolder2.js"))



if __name__ == '__main__':
    unittest.main()