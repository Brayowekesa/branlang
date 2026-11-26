# common.py
class BranError(Exception): pass
class LexerError(BranError): pass
class ParserError(BranError): pass
class InterpreterError(BranError): pass
class VMError(BranError): pass
class CompileError(VMError): pass