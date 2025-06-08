# interpreter.py (Final Corrected Version)

import math
from parser_ast import *
from lexer import TokenType
# At the top of interpreter.py
from lexer import Lexer
from parser_ast import Parser


class BranError(Exception):
    pass
class InterpreterError(Exception): pass
class ReturnValue(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value
class Environment:
    def __init__(self, enclosing=None): self.values, self.enclosing = {}, enclosing
    def define(self, name, value): self.values[name] = value
    def assign(self, name, value):
        if name in self.values: self.values[name] = value; return
        if self.enclosing is not None: self.enclosing.assign(name, value); return
        raise InterpreterError(f"Undefined variable '{name}'.")
    def get(self, name):
        if name in self.values: return self.values[name]
        if self.enclosing is not None: return self.enclosing.get(name)
        raise InterpreterError(f"Undefined variable '{name}'.")
class BranFunction:
    def __init__(self, declaration, closure):
        self.declaration = declaration
        self.closure = closure

    def __call__(self, interpreter, arguments):
        env = Environment(enclosing=self.closure)
        if len(arguments) != len(self.declaration.params):
            raise InterpreterError(f"Expected {len(self.declaration.params)} arguments but got {len(arguments)}.")
        for param, arg_val in zip(self.declaration.params, arguments):
            env.define(param.name, arg_val)
        try:
            interpreter.execute_block(self.declaration.body, env)
        except ReturnValue as ret:
            return ret.value
        return None
class BuiltInFunction:
    def __init__(self, name, fn): self.name, self.fn = name, fn
    def __call__(self, interpreter, arguments):
        try: return self.fn(arguments)
        except Exception as e: raise InterpreterError(f"Error in built-in function '{self.name}': {e}")
    def __repr__(self): return f"<builtin fn {self.name}>"

# In class Interpreter
class Interpreter:
    def __init__(self, stdin_text=""): # Add the new parameter
        self.globals = Environment()
        # Split the stdin text into a list of lines to be consumed
        self._stdin_lines = stdin_text.splitlines()
        self._stdin_index = 0
        self._module_cache = {}
        # ... (rest of the built-ins) ...
        def define_native(name, fn): self.globals.define(name, BuiltInFunction(name, fn))
        define_native("sqrt", lambda args: math.sqrt(args[0])); define_native("pow", lambda args: math.pow(args[0], args[1])); define_native("max", lambda args: max(args)); define_native("min", lambda args: min(args)); define_native("round", lambda args: round(args[0], args[1] if len(args) > 1 else 0))
        define_native("len", self._len); define_native("push", self._push); define_native("pop", self._pop)
        define_native("read_file", self._read_file)
        define_native("write_file", self._write_file)

    def _len(self, args):
        if len(args) != 1: raise InterpreterError("len() takes exactly one argument.")
        target = args[0]
        if isinstance(target, (list, str, dict)): return len(target)
        raise InterpreterError("len() only works on arrays, strings, and objects.")
    def _push(self, args):
        if len(args) != 2: raise InterpreterError("push() takes two arguments: an array and an item.")
        target_list, item = args[0], args[1]
        if not isinstance(target_list, list): raise InterpreterError("First argument to push() must be an array.")
        target_list.append(item); return None
    def _pop(self, args):
        if len(args) != 1: raise InterpreterError("pop() takes exactly one argument.")
        target_list = args[0]
        if not isinstance(target_list, list): raise InterpreterError("Argument to pop() must be an array.")
        if not target_list: raise InterpreterError("Cannot pop from an empty array.")
        return target_list.pop()
    # Add these methods inside the Interpreter class

    def _read_file(self, args):
        if len(args) != 1:
            raise InterpreterError("read_file() takes exactly one argument: a filepath.")
        filepath = args[0]
        if not isinstance(filepath, str):
            raise InterpreterError("Argument to read_file() must be a string.")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise InterpreterError(f"File not found: '{filepath}'")
        except Exception as e:
            raise InterpreterError(f"Error reading file '{filepath}': {e}")

    def _write_file(self, args):
        if len(args) != 2:
            raise InterpreterError("write_file() takes exactly two arguments: a filepath and content.")
        filepath, content = args[0], args[1]
        if not isinstance(filepath, str):
            raise InterpreterError("First argument to write_file() must be a string filepath.")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(content)) # Convert content to string just in case
            return None # write_file returns nothing
        except Exception as e:
            raise InterpreterError(f"Error writing to file '{filepath}': {e}")
        
    def interpret(self, tree):
        return self.execute_block(tree, self.globals)
    def execute_block(self, block_node, environment):
        previous_env = self.globals; self.globals = environment; last_value = None
        try:
            for statement in block_node.statements: last_value = self.visit(statement)
        finally: self.globals = previous_env
        return last_value
    def visit(self, node):
        #print(f"[TRACE] Visiting {type(node).__name__}")   ← add this
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)
    def generic_visit(self, node): raise InterpreterError(f'No visit_{type(node).__name__} method')
    def visit_Block(self, node): return self.execute_block(node, Environment(enclosing=self.globals))
    # The corrected block in visit_BinOp
    def visit_BinOp(self, node):
        left, right = self.visit(node.left), self.visit(node.right)
        op = node.op.type

        if op == TokenType.PLUS:
            # If either side is a string, perform string concatenation
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            
            # If both sides are lists, perform list concatenation
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            
            # Otherwise, perform numeric addition
            # This will raise a Python TypeError if types are incompatible (e.g., number + list)
            # which is the correct behavior.
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
    # Add this new method anywhere inside the Interpreter class
    def visit_ImportNode(self, node):
        filename = node.filename
        
        # 1. Check the cache
        if filename in self._module_cache:
            module_env = self._module_cache[filename]
        else:
            # 2. If not cached, load and execute the file
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            except FileNotFoundError:
                raise InterpreterError(f"Module not found: '{filename}'")

            # Create a new, separate interpreter to run the module
            # This ensures the module has its own clean global scope.
            module_interpreter = Interpreter()
            
            # Lex, parse, and interpret the module code
            lexer = Lexer(source_code)
            tokens = lexer.get_tokens()
            parser = Parser(tokens)
            ast = parser.parse()
            module_interpreter.interpret(ast)

            # 3. Cache the module's environment
            module_env = module_interpreter.globals
            self._module_cache[filename] = module_env

        # 4. Merge the module's exports into the current environment
        for name, value in module_env.values.items():
            self.globals.define(name, value)
    def visit_UnaryOp(self, node): val = self.visit(node.expr); return -val if node.op.type == TokenType.MINUS else val
    def visit_Number(self, node): return node.value
    def visit_String(self, node): return node.value
    def visit_Boolean(self, node): return node.value
    def visit_VarDecl(self, node):
        val = self.visit(node.expr)
        #print(f"[DEBUG] Declaring {node.name.name} = {val}")
        self.globals.define(node.name.name, val)
        return val
    def visit_VarAssign(self, node): val = self.visit(node.expr); self.globals.assign(node.name.name, val); return val
    def visit_VarAccess(self, node): return self.globals.get(node.name)
    def visit_ArrayLiteral(self, node): return [self.visit(elem) for elem in node.elements]
    def visit_ObjectLiteral(self, node):
        return {key: self.visit(value_node) for key, value_node in node.pairs.items()}
    def visit_MemberAccess(self, node):
        callee = self.visit(node.callee); key = self.visit(node.member)
        if isinstance(callee, list):
            if not isinstance(key, int): raise InterpreterError("Array index must be an integer.")
            if not (0 <= key < len(callee)): raise InterpreterError(f"Array index out of bounds: {key}")
            return callee[key]
        if isinstance(callee, dict):
            if not isinstance(key, str): raise InterpreterError("Object key must be a string.")
            return callee.get(key)
        raise InterpreterError("Can only access members of arrays and objects.")
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
        iterable_val = self.visit(node.iterable)
        var_name = node.var_name.name  # <-- FIXED HERE
    
        if isinstance(iterable_val, list):
            items_to_loop = iterable_val
        elif isinstance(iterable_val, dict):
            items_to_loop = list(iterable_val.keys())
        else:
            raise InterpreterError("Can only iterate over arrays and objects.")
    
        loop_env = Environment(enclosing=self.globals)
        self.globals = loop_env
        for item in items_to_loop:
            loop_env.define(var_name, item)
            self.visit(node.body)
        self.globals = loop_env.enclosing

    def visit_Show(self, node): print(*[self.visit(expr) for expr in node.expressions])
    def visit_When(self, node):
        if self.visit(node.condition): return self.visit(node.true_block)
        elif node.false_block: return self.visit(node.false_block)
    def visit_Loop(self, node):
        while self.visit(node.condition): self.visit(node.body)
    def visit_For(self, node):
        start, end, step, var_name = self.visit(node.start), self.visit(node.end), self.visit(node.step), node.var_name.name
        loop_env = Environment(enclosing=self.globals); self.globals = loop_env; i = start
        while (step > 0 and i <= end) or (step < 0 and i >= end):
            loop_env.define(var_name, i); self.visit(node.body); i = loop_env.get(var_name); i += step
        self.globals = loop_env.enclosing
    def visit_FnDef(self, node):
        fn_name = node.name.name
        function = BranFunction(node, self.globals)
        self.globals.define(fn_name, function)
    
    def visit_FnCall(self, node):
        # First, evaluate the callee expression to get the function object
        callee = self.visit(node.callee)
        
        # Now check if the *result* is a callable thing
        if not isinstance(callee, (BranFunction, BuiltInFunction)):
            # Create a more robust error message for when the callee isn't a simple name
            callee_name = getattr(node.callee, 'name', 'expression')
            raise InterpreterError(f"'{callee_name}' is not a callable function.")
        
        arguments = [self.visit(arg) for arg in node.args]
        return callee(self, arguments)
    
    def visit_Return(self, node):
        value = self.visit(node.expr)
        raise ReturnValue(value)
    # In class Interpreter
    def visit_Ask(self, node):
        # We still visit the prompt, so it's evaluated, but we don't display it.
        # This ensures the code remains valid even if not used in this model.
        self.visit(node.prompt)

        # Instead of calling input(), we read from our stored STDIN lines.
        if self._stdin_index >= len(self._stdin_lines):
            # If we run out of input lines, raise an error.
            raise InterpreterError("Not enough lines in STDIN to satisfy all ask() calls.")
        
        user_input = self._stdin_lines[self._stdin_index]
        self._stdin_index += 1 # Move to the next line for the next ask() call

        # The rest of the type conversion logic remains the same
        if node.numeric_type == 'int':
            try:
                return int(user_input)
            except ValueError:
                raise InterpreterError(f"Invalid integer input from STDIN: '{user_input}'")
        elif node.numeric_type == 'float':
            try:
                return float(user_input)
            except ValueError:
                raise InterpreterError(f"Invalid float input from STDIN: '{user_input}'")
        else:
            return user_input