# common.py - Shared classes for the BranLang interpreter

class BranError(Exception):
    """Base class for all BranLang errors."""
    pass

class LexerError(BranError): pass
class ParserError(BranError): pass
class InterpreterError(BranError): pass