import os
import sys
from lexer import Lexer, LexerError
from parser_ast import Parser, ParserError
from interpreter import Interpreter, InterpreterError
from vm import Compiler, VM, VMError

ENGINES = ('ast', 'vm')
# Default engine; override with --ast / --vm or the BRANLANG_ENGINE env var.
DEFAULT_ENGINE = os.environ.get('BRANLANG_ENGINE', 'vm')

def run(source_code, stdin_text=None, engine=None, disassemble=False):
    engine = engine or DEFAULT_ENGINE
    if engine not in ENGINES:
        raise ValueError(f"Unknown engine '{engine}' (expected one of {ENGINES})")
    try:
        lexer = Lexer(source_code)
        tokens = lexer.get_tokens()
        parser = Parser(tokens)
        ast = parser.parse()
        if engine == 'vm' or disassemble:
            script = Compiler().compile(ast)
            if disassemble:
                from bytecode import disassemble as dis
                dis(script); return
            VM(script, stdin_text=stdin_text).run()
        else:
            Interpreter(stdin_text=stdin_text).interpret(ast)
    except RecursionError:
        e = InterpreterError("Maximum recursion depth exceeded.")
        print(f"BranLang Error: {e}", file=sys.stderr); raise e
    except (LexerError, ParserError, InterpreterError, VMError) as e:
        print(f"BranLang Error: {e}", file=sys.stderr)
        raise

def run_file(filename, stdin_text=None, engine=None, disassemble=False):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found '{filename}'", file=sys.stderr)
        sys.exit(1)
    run(source_code, stdin_text=stdin_text, engine=engine, disassemble=disassemble)

if __name__ == '__main__':
    args = sys.argv[1:]
    engine = None
    for flag in ('--ast', '--vm'):
        if flag in args:
            engine = flag[2:]
            args.remove(flag)
    disassemble = '--dis' in args
    if disassemble:
        args.remove('--dis')
    if len(args) != 1:
        print("Usage: python branlang.py [--vm | --ast] [--dis] <filename.bl>  (default: --vm)")
        sys.exit(1)
    filename = args[0]
    stdin_text = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped is not None:
            stdin_text = piped
    try:
        run_file(filename, stdin_text=stdin_text, engine=engine, disassemble=disassemble)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
