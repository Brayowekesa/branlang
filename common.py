# common.py
class BranError(Exception): pass
class LexerError(BranError): pass
class ParserError(BranError): pass
class InterpreterError(BranError): pass