import ast
import os

from .lexer import lexers
from .parser import parsers
from .utils.astpp import dump as ast_dump
from .utils.parser import ParserState, build_call, build_str_join


AST_DEBUG = os.environ.get('RATTLE_AST_DEBUG', False)
SHOW_CODE = os.environ.get('RATTLE_SHOW_CODE', False)


class TemplateSyntaxError(Exception):
    pass


class SafeData(str):
    """
    A wrapper for str to indicate it doesn't need escaping.
    """
    pass


def escape(text):
    """
    Returns the given text with ampersands, quotes and angle brackets encoded
    for use in HTML.
    """
    if isinstance(text, SafeData):
        return text
    if not isinstance(text, str):
        text = str(text)
    return SafeData(
        text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&#39;')
    )


def auto_escape(s):
    if isinstance(s, SafeData):
        return s
    return escape(s)


class Library(object):

    def __init__(self):
        self._filters = {}
        self._tags = {}
        self._ambiguous_filters = set()
        self._ambiguous_tags = set()

    @property
    def filters(self):
        return self._filters

    @property
    def tags(self):
        return self._tags

    def register_filter(self, func):
        name = func.__name__
        full_name = '%s.%s' % (func.__module__, func.__name__)
        if name not in self._filters:
            if name not in self._ambiguous_filters:
                self._filters[func.__name__] = func
        elif full_name not in self._filters:
            self._ambiguous_filters.add(name)
            del self._filters[name]
        self._filters[full_name] = func
        # Allows use as decorator
        return func

    def unregister_filter(self, full_name):
        self._filters.pop(full_name, None)
        _, _, short_name = full_name.rpartition('.')
        self._filters.pop(short_name, None)

    def register_tag(self, func):
        name = func.__name__
        full_name = '%s.%s' % (func.__module__, func.__name__)
        if name not in self._tags:
            if name not in self._ambiguous_tags:
                self._tags[func.__name__] = func
        elif full_name not in self._tags:
            self._ambiguous_tags.add(name)
            del self._tags[name]
        self._tags[full_name] = func
        # Allows use as decorator
        return func

    def unregister_tag(self, full_name):
        self._tags.pop(full_name, None)
        _, _, short_name = full_name.rpartition('.')
        self._tags.pop(short_name, None)


library = Library()


class Template(object):

    def __init__(self, source, origin=None):
        self.source = source
        self.origin = origin

        # A list of compiled tags
        self.compiled_tags = []

        code = self.parse()
        ast.fix_missing_locations(code)
        if AST_DEBUG:
            print(ast_dump(code))
        if SHOW_CODE:
            try:
                import codegen
                print(codegen.to_source(code))
            except ImportError:
                pass
        self.func = compile(code, filename="<template>", mode="exec")

        self.default_context = {
            'True': True,
            'False': False,
            'None': None,
        }

    def parse(self):
        """
        Convert the parsed tokens into a list of expressions then join them
        """
        tokens = lexers.sl.lex(self.source)
        state = ParserState()
        klass = parsers.sp.parse(tokens, state)
        state.finalize()
        body = [
            klass,
            ast.Global(names=['rendered']),
            ast.Assign(
                targets=[ast.Name(id='rendered', ctx=ast.Store())],
                value=build_str_join(
                    build_call(
                        ast.Attribute(
                            value=build_call(
                                ast.Name(id='Template', ctx=ast.Load())
                            ),
                            attr='root',
                            ctx=ast.Load()
                        ),
                        args=[
                            ast.Name(id='context', ctx=ast.Load())
                        ],
                    )
                )
            )
        ]
        return ast.Module(
            body=body
        )

    def render(self, context={}):
        ctx = context.copy()
        ctx.update(self.default_context)
        global_ctx = {
            'context': ctx,
            'compiled_tags': self.compiled_tags,
            'filters': library.filters,
            'auto_escape': auto_escape,
            'output': [],
            'rendered': None
        }
        local_ctx = {
        }
        eval(self.func, global_ctx, local_ctx)
        return global_ctx['rendered']
