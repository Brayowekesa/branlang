# interpreter.py
import math
from lexer import Lexer, TokenType
from parser_ast import Parser, VarAccess, MemberAccess
from common import InterpreterError, BranError

class ReturnValue(Exception):
    def __init__(self, value): self.value = value
class BreakException(Exception): pass
class ContinueException(Exception): pass
class Environment:
    def __init__(self, enclosing=None):
        self.values, self.enclosing = {}, enclosing
    def define(self, name, value, is_constant=False):
        self.values[name] = (value, is_constant)
    def assign(self, name, value):
        if name in self.values:
            _, is_constant = self.values[name]
            if is_constant: raise InterpreterError(f"Cannot assign to constant '{name}'.")
            self.values[name] = (value, False); return
        if self.enclosing is not None: self.enclosing.assign(name, value); return
        raise InterpreterError(f"Undefined variable '{name}'.")
    def get(self, name):
        if name in self.values:
            val, _ = self.values[name]; return val
        if self.enclosing is not None: return self.enclosing.get(name)
        raise InterpreterError(f"Undefined variable '{name}'.")

class Callable:
    def __call__(self, interpreter, arguments): raise NotImplementedError
class BranFunction(Callable):
    def __init__(self, declaration, closure): self.declaration, self.closure = declaration, closure
    def __call__(self, interpreter, arguments):
        env = Environment(enclosing=self.closure)
        if len(self.declaration.params) != len(arguments): raise InterpreterError(f"Expected {len(self.declaration.params)} arguments but got {len(arguments)}.")
        for param, arg_val in zip(self.declaration.params, arguments):
            env.define(param.name, arg_val)
        try:
            interpreter.execute_block(self.declaration.body, env)
        except ReturnValue as ret: return ret.value
        return None
    def __repr__(self): return f"<fn {self.declaration.name_node.name}>"
class BuiltInFunction(Callable):
    def __init__(self, name, function): self.name, self.function = name, function
    def __call__(self, interpreter, arguments): return self.function(arguments)
    def __repr__(self): return f"<builtin fn {self.name}>"
class BoundMethod(Callable):
    def __init__(self, obj, method_name):
        self.obj, self.method_name = obj, method_name
    def __call__(self, interpreter, arguments):
        # This is where we'll dispatch to the actual string methods
        return interpreter._call_string_method(self.obj, self.method_name, arguments)

class Interpreter:
    def __init__(self, stdin_text=None):
        self.globals = Environment()
        self._module_cache = {}
        self._interactive_mode = stdin_text is None
        self._stdin_lines = stdin_text.splitlines() if stdin_text is not None else []
        self._stdin_index = 0
        self._define_builtins()
    def _define_builtins(self):
        def define_native(name, fn): self.globals.define(name, BuiltInFunction(name, fn), is_constant=True)
        # Math functions
        define_native("sqrt", lambda args: math.sqrt(args[0]))
        define_native("pow", lambda args: math.pow(args[0], args[1]))
        define_native("max", lambda args: max(args[0] if len(args) == 1 and isinstance(args[0], list) else args))
        define_native("min", lambda args: min(args[0] if len(args) == 1 and isinstance(args[0], list) else args))
        define_native("round", lambda args: round(args[0], args[1] if len(args) > 1 else 0))
        # Array, string, and file functions
        define_native("len", self._len); define_native("push", self._push); define_native("pop", self._pop)
        define_native("read_file", self._read_file); define_native("write_file", self._write_file)
    def _len(self, args):
        if len(args) != 1: raise InterpreterError("len() takes exactly one argument.")
        if isinstance(args[0], (list, str, dict)): return len(args[0])
        raise InterpreterError("len() only works on arrays, strings, and objects.")
    def _push(self, args):
        if len(args) != 2: raise InterpreterError("push() takes two arguments: an array and an item.")
        if not isinstance(args[0], list): raise InterpreterError("First argument to push() must be an array.")
        args[0].append(args[1]); return None
    def _pop(self, args):
        if len(args) != 1: raise InterpreterError("pop() takes exactly one argument.")
        if not isinstance(args[0], list): raise InterpreterError("Argument to pop() must be an array.")
        if not args[0]: raise InterpreterError("Cannot pop from an empty array.")
        return args[0].pop()
    def _read_file(self, args):
        if len(args) != 1 or not isinstance(args[0], str): raise InterpreterError("read_file() takes one string argument: a filepath.")
        try:
            with open(args[0], 'r', encoding='utf-8') as f: return f.read()
        except FileNotFoundError: raise InterpreterError(f"File not found: '{args[0]}'")
        except Exception as e: raise InterpreterError(f"Error reading file '{args[0]}': {e}")
    def _write_file(self, args):
        if len(args) != 2 or not isinstance(args[0], str): raise InterpreterError("write_file() takes two arguments: a filepath and content.")
        try:
            with open(args[0], 'w', encoding='utf-8') as f: f.write(str(args[1]))
            return None
        except Exception as e: raise InterpreterError(f"Error writing to file '{args[0]}': {e}")
    def interpret(self, tree):
        try: return self.execute_block(tree, self.globals)
        except ReturnValue: raise InterpreterError("Return statement used outside of a function.")
    def execute_block(self, block_node, environment):
        previous_env = self.globals; self.globals = environment; last_value = None
        try:
            for statement in block_node.statements: last_value = self.visit(statement)
        finally: self.globals = previous_env
        return last_value
    def visit(self, node):
        method_name = f'visit_{type(node).__name__}'; visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)
    def generic_visit(self, node): raise InterpreterError(f'No visit_{type(node).__name__} method')
    def visit_Block(self, node): return self.execute_block(node, Environment(enclosing=self.globals))
    def visit_BinOp(self, node):
        left, right = self.visit(node.left), self.visit(node.right); op = node.op.type
        if op == TokenType.PLUS:
            if isinstance(left, str) or isinstance(right, str): return str(left) + str(right)
            if isinstance(left, list) and isinstance(right, list): return left + right
            return left + right
        if op == TokenType.MINUS: return left - right
        if op == TokenType.MUL: return left * right
        if op == TokenType.DIV:
            if right == 0: raise InterpreterError("Division by zero.")
            return left / right
        if op == TokenType.MOD: return left % right
        if op == TokenType.POW: return left ** right
        if op == TokenType.EQ: return left == right
        if op == TokenType.NE: return left != right
        if op == TokenType.LT: return left < right
        if op == TokenType.GT: return left > right
        if op == TokenType.LTE: return left <= right
        if op == TokenType.GTE: return left >= right
        if op == TokenType.AND: return bool(left and right)
        if op == TokenType.OR: return bool(left or right)
        if op == TokenType.NULL_COALESCE: return left if left is not None else right
    def visit_UnaryOp(self, node): val = self.visit(node.expr); return -val if node.op.type == TokenType.MINUS else val
    def visit_Number(self, node): return node.value
    def visit_String(self, node): return node.value
    def visit_Boolean(self, node): return node.value
    def visit_NullNode(self, node): return None
    def visit_VarDecl(self, node): val = self.visit(node.expr); self.globals.define(node.name_node.name, val); return val
    def visit_ConstDecl(self, node):
        val = self.visit(node.expr)
        self.globals.define(node.name_node.name, val, is_constant=True); return val
    def visit_VarAssign(self, node): val = self.visit(node.expr); self.globals.assign(node.name_node.name, val); return val
    def visit_VarAccess(self, node): return self.globals.get(node.name)
    def visit_ArrayLiteral(self, node): return [self.visit(elem) for elem in node.elements]
    def visit_ObjectLiteral(self, node): return {key: self.visit(value_node) for key, value_node in node.pairs.items()}
    def visit_MemberAccess(self, node):
        callee = self.visit(node.callee); key = self.visit(node.member)
        if isinstance(callee, list):
            if not isinstance(key, int): raise InterpreterError("Array index must be an integer.")
            if not (0 <= key < len(callee)): raise InterpreterError(f"Array index out of bounds: {key}")
            return callee[key]
        if isinstance(callee, dict):
            if not isinstance(key, str): raise InterpreterError("Object key must be a string.")
            return callee.get(key)
        if isinstance(callee, str):
            return BoundMethod(callee, key)
        raise InterpreterError("Can only access members of arrays, objects, and strings.")
    def visit_MemberAssign(self, node):
        callee = self.visit(node.callee); key = self.visit(node.member); value = self.visit(node.value)
        if isinstance(callee, dict):
            if not isinstance(key, str): raise InterpreterError("Object key must be a string.")
            callee[key] = value; return value
        if isinstance(callee, list):
            if not isinstance(key, int): raise InterpreterError("Array index must be an integer.")
            if not (0 <= key < len(callee)): raise InterpreterError(f"Array index out of bounds: {key}")
            callee[key] = value; return value
        raise InterpreterError("Can only assign to members of arrays and objects.")
    def visit_ForEach(self, node):
        iterable = self.visit(node.iterable)

        if isinstance(iterable, list):
            for item in iterable:
                try:
                    env = Environment(enclosing=self.globals)
                    env.define(node.var_name_node.name, item)
                    self.execute_block(node.body, env)
                except ContinueException: continue
                except BreakException: break

        elif isinstance(iterable, dict):
            # iterate over keys of the object
            for key in iterable.keys():
                try:
                    env = Environment(enclosing=self.globals)
                    env.define(node.var_name_node.name, key)
                    self.execute_block(node.body, env)
                except ContinueException: continue
                except BreakException: break

        else:
            raise InterpreterError("ForEach only works on arrays and objects.")

    def visit_Show(self, node): print(*[self.visit(expr) for expr in node.expressions])
    def visit_When(self, node):
        if self.visit(node.condition): return self.visit(node.true_block)
        elif node.false_block: return self.visit(node.false_block)
    def visit_Loop(self, node):
        while self.visit(node.condition):
            try: self.visit(node.body)
            except ContinueException: continue
            except BreakException: break
    def visit_For(self, node):
        start, end, step, var_name = self.visit(node.start), self.visit(node.end), self.visit(node.step), node.var_name_node.name
        i = start
        # Create a new environment for each iteration to ensure proper scoping
        while (step > 0 and i <= end) or (step < 0 and i >= end):
            try:
                env = Environment(enclosing=self.globals)
                env.define(var_name, i)
                self.execute_block(node.body, env)
            except ContinueException: i += step; continue
            except BreakException: break
            i += step
    def visit_FnDef(self, node):
        function = BranFunction(node, self.globals); self.globals.define(node.name_node.name, function)
    def _call_string_method(self, string_obj, method_name, args):
        if method_name == "upper": return string_obj.upper()
        if method_name == "lower": return string_obj.lower()
        if method_name == "trim": return string_obj.strip()
        if method_name == "contains":
            if not args: raise InterpreterError("contains() requires one argument.")
            return args[0] in string_obj
        if method_name == "split": return string_obj.split(args[0] if args else " ")
        if method_name == "replace":
            if len(args) != 2: raise InterpreterError("replace() requires two arguments.")
            return string_obj.replace(args[0], args[1])
        raise InterpreterError(f"String has no method named '{method_name}'.")
    def visit_FnCall(self, node):
        callee = self.visit(node.callee); arguments = [self.visit(arg) for arg in node.args]
        if isinstance(callee, Callable): return callee(self, arguments)
        callee_name = getattr(node.callee, 'name', 'expression'); raise InterpreterError(f"'{callee_name}' is not a callable function.")
    def visit_TryCatch(self, node):
        try:
            return self.visit(node.try_block)
        except InterpreterError as e:
            catch_env = Environment(enclosing=self.globals)
            error_message = str(e)
            catch_env.define(node.error_var_node.name, error_message)
            return self.execute_block(node.catch_block, catch_env)
    def visit_BreakNode(self, node): raise BreakException()
    def visit_ContinueNode(self, node): raise ContinueException()
    def visit_ImportNode(self, node):
        filename = node.filename
        if filename in self._module_cache:
            env = self._module_cache[filename]
        else:
            try:
                with open(filename, 'r', encoding='utf-8') as f: code = f.read()
            except FileNotFoundError: raise InterpreterError(f"Module not found: '{filename}'")
            
            module_interpreter = Interpreter()
            # Use the same stdin context for the module
            module_interpreter._stdin_lines = self._stdin_lines
            module_interpreter._stdin_index = self._stdin_index
            
            lexer = Lexer(code); tokens = lexer.get_tokens(); parser = Parser(tokens); ast = parser.parse()
            module_interpreter.interpret(ast)
            env = module_interpreter.globals
            self._module_cache[filename] = env
        for name, (value, is_const) in env.values.items():
            self.globals.define(name, value, is_constant=is_const)
    def visit_Return(self, node): raise ReturnValue(self.visit(node.expr))
    def visit_Ask(self, node):
        prompt_text = self.visit(node.prompt) if node.prompt else ""

        if self._interactive_mode:
            user_input = input(prompt_text)
        else:
            if self._stdin_index >= len(self._stdin_lines):
                raise InterpreterError("No more input available.")
            user_input = self._stdin_lines[self._stdin_index]
            self._stdin_index += 1

        try:
            if node.numeric_type == "int":
                return int(user_input)
            elif node.numeric_type == "float":
                return float(user_input)
            else:
                return user_input
        except Exception:
            # Instead of crashing, raise so try/catch can handle it
            raise InterpreterError(
                f"Invalid {node.numeric_type or 'string'} input: '{user_input}'"
            )
