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
        f = open("views/__js__/subfolder_%s.js" % fileName)
        compiled_javascript = "".join(f.readlines())
        f.close()
        compiled_javascript = re.sub("\s\s+", "", compiled_javascript).replace("\n", "").rstrip(";")

        compiled_javascript = re.search("return (.+)},", compiled_javascript, re.DOTALL).group(1)
        if debug:
            print("JS: ", compiled_javascript)

        executed_javascript = self.executeJavascript(z9_suit_js, compiled_javascript, data)
        executed_javascript = filterForExecuted(
            executed_javascript
        ) if filterForExecuted is not None else executed_javascript

        # Основная проверка результатов выполнения
        expected = filterForExecuted(expected) if filterForExecuted is not None else expected

        checker = self.assertEqual if not check_with else check_with
        checker(expected, executed_python)
        checker(expected, executed_javascript)

    def executeJavascript(self, z9source, compiled, data):
        f = open("current.js", "w+")
        f.writelines(
            '''%s(%s)''' % (
                '''(function(data) {%s print(%s);})''' % (z9source, compiled),
                json.dumps(data, default=json_dumps_handler)
            )
        )
        f.close()
        # print('''%s(%s)''' % (
        #     '''(function(data) {%s print(%s);})''' % (z9source, compiled),
        #     json.dumps(data, default=json_dumps_handler)
        # ))

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

    def test_breakPoint_include(self):
        """
        Сделаем простое включение одного шаблона в другой

        """
        inc_template = '''-<var>a</var>-'''
        template1 = '''a=<var>a</var>: 1<breakpoint include="subfolder.inc_template"></breakpoint>3'''
        template2 = '''a=<var>a</var>: 1<breakpoint include="subfolder.inc_template">{"a": 0}</breakpoint>3'''
        template3 = '''a=<var>a</var>: 1<breakpoint include="subfolder.inc_template">{"a": <var>a</var>}</breakpoint>3'''

        # Запишем оба шаблона в файлы
        self.assertFalse(os.path.isfile("views/subfolder/inc_template.html"))
        f = open("views/subfolder/inc_template.html", "w+")
        f.writelines(inc_template)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/inc_template.html"))

        self.assertFalse(os.path.isfile("views/subfolder/template_1.html"))
        f = open("views/subfolder/template_1.html", "w+")
        f.writelines(template1)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template_1.html"))

        self.assertFalse(os.path.isfile("views/subfolder/template_2.html"))
        f = open("views/subfolder/template_2.html", "w+")
        f.writelines(template2)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template_2.html"))

        self.assertFalse(os.path.isfile("views/subfolder/template_3.html"))
        f = open("views/subfolder/template_3.html", "w+")
        f.writelines(template3)
        f.close()
        self.assertTrue(os.path.isfile("views/subfolder/template_3.html"))

        # И скомпилируем их
        os.chdir("views")
        self.c.compile()
        os.chdir("../")

        # Проверим включаемый шаблон (особого интереса не представляет)
        self.assertEqual(Suit("views.subfolder.inc_template").execute({"a": 1}), "-1-")
        self.assertEqual(Suit("views.subfolder.inc_template").execute({"a": 2}), "-2-")

        # template_1 содержит традиционное включение (в рамках этого теста тоже интереса не много)
        self.assertEqual(Suit("views.subfolder.template_1").execute({"a": 1}), "a=1: 1-1-3")
        self.assertEqual(Suit("views.subfolder.template_1").execute({"a": 2}), "a=2: 1-2-3")

        # А вот template_2 - самое интересное:
        self.assertEqual(Suit("views.subfolder.template_2").execute({"a": 1}), "a=1: 1-0-3")
        self.assertEqual(Suit("views.subfolder.template_2").execute({"a": 2}), "a=2: 1-0-3")

        # И шаблон template_3 еще интереснее:
        self.assertEqual(Suit("views.subfolder.template_3").execute({"a": 1}), "a=1: 1-1-3")
        self.assertEqual(Suit("views.subfolder.template_3").execute({"a": 2}), "a=2: 1-2-3")





if __name__ == '__main__':
    unittest.main()

