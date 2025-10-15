import sys
from lexer import Lexer, LexerError
from parser_ast import Parser, ParserError
from interpreter import Interpreter, InterpreterError

def run(source_code, stdin_text=None):
    try:
        lexer = Lexer(source_code)
        tokens = lexer.get_tokens()
        parser = Parser(tokens)
        ast = parser.parse()
        interpreter = Interpreter(stdin_text=stdin_text)
        interpreter.interpret(ast)
    except RecursionError:
        e = InterpreterError("Maximum recursion depth exceeded.")
        print(f"BranLang Error: {e}", file=sys.stderr); raise e
    except (LexerError, ParserError, InterpreterError) as e:
        print(f"BranLang Error: {e}", file=sys.stderr)
        raise

def run_file(filename, stdin_text=None):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found '{filename}'", file=sys.stderr)
        sys.exit(1)
    run(source_code, stdin_text=stdin_text)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python branlang.py <filename.bl>")
        sys.exit(1)
    filename = sys.argv[1]
    stdin_text = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped is not None:
            stdin_text = piped
    try:
        run_file(filename, stdin_text=stdin_text)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
