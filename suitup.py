#!/usr/bin/env python3
# coding=utf-8

"""
Библиотека z9 >> standalone компилятор для шаблонизатор Suit

Автор: Андрей Юрьев
Дата:  июнь 2013

"""

from suit.Suit import Compiler


def main():
    """
    Основное метод компилятора

    """
    c = Compiler()
    c.compile()
    c.build()


if __name__ == '__main__':
    main()
