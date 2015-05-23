"""
    Unit tests for Suit template engine

"""

import unittest
import os
import re
import hashlib
import json
import subprocess

from datetime import datetime, date, time


from suit.Suit import XmlTag, PythonSyntax, JavascriptSyntax, Compiler, Suit, suit, trimSpaces, json_dumps_handler


# Получаем результат выполнения скомпилированного js кода
# Для этого потребуется js-библиотека z9:
with open("%s/../Suit.js" % os.path.dirname(os.path.realpath(__file__))) as f:
    z9_suit_js = f.read()


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

    def simulate(self, template, expected, data=None, name=None, filterForExecuted=None, check_with=None, debug=False):
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
        self.c.build()
        os.chdir("../")
        if debug:
            # Получаем скомпилированный python ход
            f = open("views/__py__/subfolder_%s.py" % fileName)
            compiled_python = "".join(f.readlines())
            compiled_python = re.search("return \((.+)\)", compiled_python).group(1)
            f.close()
            print("PY: ", compiled_python)

        # Получам результат выполнения скомпилированного python кода
        executed_python = Suit("views.subfolder.%s" % fileName).execute(data)
        executed_python = filterForExecuted(executed_python) if filterForExecuted is not None else executed_python

        # Получаем скомпилированный js код
        f = open("views/__js__/all.js")
        compiled_javascript = "".join(f.readlines())
        f.close()
        compiled_javascript = re.sub("\s\s+", "", compiled_javascript).replace("\n", "").rstrip(";")
        if debug:
            print("JS: ", compiled_javascript)

        executed_javascript = self.executeJavascript(z9_suit_js + compiled_javascript + ";", fileName, data)
        executed_javascript = filterForExecuted(
            executed_javascript
        ) if filterForExecuted is not None else executed_javascript

        # Основная проверка результатов выполнения
        expected = filterForExecuted(expected) if filterForExecuted is not None else expected

        checker = self.assertEqual if not check_with else check_with
        checker(expected, executed_python)
        checker(expected, executed_javascript)

    def executeJavascript(self, z9source, tn, data):
        f = open("current.js", "w+")
        f.writelines(
            '''%s(%s)''' % (
                '''(function(data) {%s print(suit.template("subfolder.%s").execute(data));})''' % (z9source, tn),
                json.dumps(data, default=json_dumps_handler)
            )
        )
        f.close()

        sp = subprocess.Popen('''java -cp . RunScriptDemo 'current.js' ''', shell=True, stdout=subprocess.PIPE, cwd=os.path.dirname(os.path.realpath(__file__)))
        res = ""
        s = True
        while s:
            s = sp.stdout.readline()
            res += s.decode('utf-8')
        sp.stdout.close()
        return res.strip()

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

    def test_breakPoint_include_with_params(self):
        """ Тестируем включение шаблонов с передачей в них параметров """
        inc_template = '''-<var>a</var>-'''
        template1 = '''a=<var>a</var>: 1<breakpoint include="subfolder.inc_template"></breakpoint>3'''
        template2 = '''a=<var>a</var>: 1<breakpoint include="subfolder.inc_template">{"a": 0}</breakpoint>3'''
        template3 = '''a=<var>a</var>: 1<breakpoint include="subfolder.inc_template">{"a": <var>a</var>}</breakpoint>3'''

        # Проверим включаемый шаблон (особого интереса не представляет)
        self.simulate(inc_template, "-1-", {"a": 1}, name="inc_template")
        self.simulate(inc_template, "-2-", {"a": 2}, name="inc_template2")

        # template_1 содержит традиционное включение (в рамках этого теста тоже интереса не много)
        self.simulate(template1, "a=1: 1-1-3", {"a": 1})
        self.simulate(template1, "a=2: 1-2-3", {"a": 2})

        # А вот template_2 - самое интересное:
        self.simulate(template2, "a=1: 1-0-3", {"a": 1})
        self.simulate(template2, "a=2: 1-0-3", {"a": 2})

        # И шаблон template_3 еще интереснее:
        self.simulate(template3, "a=1: 1-1-3", {"a": 1})
        self.simulate(template3, "a=2: 1-2-3", {"a": 2})
        self.simulate(template3, "a=4: 1-4-3", {"a": 4})

    def test_breakPoint_include_with_params_in_list(self):
        """ Тестируем включение шаблонов и передачу в них параметров из переменных цикла """
        inc_template = '''-<var>a</var>-'''
        list_template1 = '''<list for="user" in="users"><breakpoint include="subfolder.inc_template"></breakpoint></list>'''
        list_template2 = '''<list for="user" in="users"><breakpoint include="subfolder.inc_template">{"a": "<var>user</var>"}</breakpoint></list>'''

        # Проверим включаемый шаблон (особого интереса не представляет)
        self.simulate(inc_template, "-1-", {"a": 1}, name="inc_template")
        self.simulate(inc_template, "-2-", {"a": 2}, name="inc_template2")

        # Проверим обычную (сквозную передачу параметра из контроллера во включаемый шаблон:
        self.simulate(list_template1, "-1--1-", {"users": ["Andrey", "Nikolay"], "a": 1})
        self.simulate(list_template2, "-Andrey--Nikolay-", {"users": ["Andrey", "Nikolay"], "a": 1})




if __name__ == '__main__':
    unittest.main()

