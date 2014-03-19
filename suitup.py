#!/usr/bin/env python3
# coding=utf-8

"""
standalone компилятор для шаблонизатор Suit

"""
import os
from sys import argv

from suit.Suit import Compiler


def main():
    """
    Основное метод компилятора

    """
    c = Compiler()
    c.compile()
    c.build()


if __name__ == '__main__':
    path = argv[1] if len(argv) > 1 else None
    if path:
        os.chdir(path)
    main()
