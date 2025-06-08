# branlang.py (Main entry point)

import sys
from lexer import Lexer, LexerError
from parser_ast import Parser, ParserError
from interpreter import Interpreter, InterpreterError

def run(source_code):
    try:
        lexer = Lexer(source_code)
        tokens = lexer.get_tokens()
        #print(tokens)    
        parser = Parser(tokens)
        ast = parser.parse()
        # Debug: list out all top-level statements the parser saw
        #stmt_types = [type(stmt).__name__ for stmt in ast.statements]
        #print(f"[AST] Top-level statements ({len(stmt_types)}): {stmt_types}")
        interpreter = Interpreter()
        interpreter.interpret(ast)
    except (LexerError, ParserError, InterpreterError) as e:
        print(f"BranLang Error: {e}")   # Now prints to stdout
        sys.exit(1)

def run_file(filename):
    try:
        # --- THIS IS THE ONLY CHANGE IN THIS FILE ---
        with open(filename, 'r', encoding='utf-8') as f:
            source_code = f.read()
        run(source_code)
    except FileNotFoundError:
        print(f"Error: File not found '{filename}'", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python branlang.py <filename.bl>")
        sys.exit(1)
    
    filename = sys.argv[1]
    run_file(filename)