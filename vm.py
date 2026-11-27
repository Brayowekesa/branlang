# vm.py - stack-based virtual machine that runs compiled BranLang bytecode
import math
from common import BranError, VMError, CompileError
from bytecode import Op, NativeFunction, Closure, Upvalue
from compiler import Compiler

__all__ = ['VM', 'VMError', 'CompileError', 'Compiler']

MAX_FRAMES = 1000

# Opcode values unpacked into locals at the top of VM._execute (same order as there).
_OPCODE_VALUES = tuple(int(Op[name]) for name in (
    'ADD', 'AND', 'ASK', 'BUILD_LIST', 'BUILD_MAP', 'CALL', 'COALESCE', 'CONST',
    'DEFINE_CONST', 'DEFINE_GLOBAL', 'DIV', 'EQ', 'FALSE', 'FOR_ITER', 'GET_GLOBAL',
    'GET_INDEX', 'GET_ITER', 'GET_LOCAL', 'GT', 'GTE', 'HALT', 'IMPORT', 'JUMP',
    'JUMP_IF_FALSE', 'LOOP', 'LT', 'LTE', 'MOD', 'MUL', 'NE', 'NEGATE', 'NULL', 'OR', 'POP',
    'POP_TRY', 'POW', 'PRINT_N', 'RAISE', 'RANGE_COND', 'RETURN', 'SETUP_TRY', 'SET_GLOBAL',
    'SET_INDEX', 'SET_LOCAL', 'SUB', 'TRUE', 'CLOSURE', 'GET_UPVALUE', 'SET_UPVALUE',
    'CLOSE_UPVALUE', 'CLOSE_FROM', 'CLASS', 'INHERIT', 'METHOD', 'GET_SUPER'))


class CallFrame:
    __slots__ = ('closure', 'function', 'ip', 'base')

    def __init__(self, closure, base):
        self.closure, self.function, self.ip, self.base = closure, closure.function, 0, base


class TryHandler:
    __slots__ = ('frame_count', 'stack_len', 'handler_ip')

    def __init__(self, frame_count, stack_len, handler_ip):
        self.frame_count, self.stack_len, self.handler_ip = frame_count, stack_len, handler_ip


# VMs currently running, innermost last. Operator overloading is triggered by
# Python operators inside the dispatch loop, so the instance needs a way back
# into the VM that is executing it.
_ACTIVE_VMS = []

BINARY_DUNDERS = {
    '__add__': ('+', '__radd__'), '__sub__': ('-', '__rsub__'), '__mul__': ('*', '__rmul__'),
    '__div__': ('/', '__rdiv__'), '__mod__': ('%', None), '__pow__': ('**', None),
    '__lt__': ('<', None), '__gt__': ('>', None), '__le__': ('<=', None), '__ge__': ('>=', None),
}


class ObjClass:
    def __init__(self, name):
        self.name, self.methods, self.superclass = name, {}, None

    def __repr__(self):
        return f"<class {self.name}>"


class ObjBoundMethod:
    """A method looked up on an instance (or via super), remembering its receiver."""
    __slots__ = ('receiver', 'method')

    def __init__(self, receiver, method):
        self.receiver, self.method = receiver, method

    def __repr__(self):
        return f"<fn {self.method.function.name}>"


class ObjInstance:
    """An instance of a BranLang class. Python operators on it dispatch to the
    class's __add__, __eq__, __str__, ... methods, run by the active VM."""
    __slots__ = ('klass', 'fields')

    def __init__(self, klass):
        self.klass, self.fields = klass, {}

    def _call(self, name, args):
        return _ACTIVE_VMS[-1].call_method(self, self.klass.methods[name], args)

    def _binary(self, name, other):
        if name in self.klass.methods:
            return self._call(name, [other])
        symbol, reflected = BINARY_DUNDERS[name]
        if reflected and isinstance(other, ObjInstance) and reflected in other.klass.methods:
            return other._call(reflected, [self])
        raise VMError(f"Unsupported operand for {symbol}: '{self.klass.name}' instance has no {name} method.")

    def _reflected(self, name, other):
        symbol = {'__radd__': '+', '__rsub__': '-', '__rmul__': '*', '__rdiv__': '/'}[name]
        if name in self.klass.methods:
            return self._call(name, [other])
        raise VMError(f"Unsupported operand for {symbol}: '{self.klass.name}' instance has no {name} method.")

    def __add__(self, other): return self._binary('__add__', other)
    def __sub__(self, other): return self._binary('__sub__', other)
    def __mul__(self, other): return self._binary('__mul__', other)
    def __truediv__(self, other): return self._binary('__div__', other)
    def __mod__(self, other): return self._binary('__mod__', other)
    def __pow__(self, other): return self._binary('__pow__', other)
    def __lt__(self, other): return self._binary('__lt__', other)
    def __gt__(self, other): return self._binary('__gt__', other)
    def __le__(self, other): return self._binary('__le__', other)
    def __ge__(self, other): return self._binary('__ge__', other)
    def __radd__(self, other): return self._reflected('__radd__', other)
    def __rsub__(self, other): return self._reflected('__rsub__', other)
    def __rmul__(self, other): return self._reflected('__rmul__', other)
    def __rtruediv__(self, other): return self._reflected('__rdiv__', other)

    def __neg__(self):
        if '__neg__' in self.klass.methods:
            return self._call('__neg__', [])
        raise VMError(f"Unsupported operand for unary -: '{self.klass.name}' instance has no __neg__ method.")

    def __eq__(self, other):
        if '__eq__' in self.klass.methods:
            return self._call('__eq__', [other])
        return self is other

    def __ne__(self, other):
        if '__ne__' in self.klass.methods:
            return self._call('__ne__', [other])
        if '__eq__' in self.klass.methods:
            return not self._call('__eq__', [other])
        return self is not other

    __hash__ = object.__hash__

    def __str__(self):
        if '__str__' in self.klass.methods:
            return str(self._call('__str__', []))
        return f"<{self.klass.name} instance>"

    __repr__ = __str__


def _is_private(key):
    return key.startswith('_') and not (key.startswith('__') and key.endswith('__'))


class InputState:
    """stdin handling shared with imported modules. None => interactive (input())."""
    def __init__(self, stdin_text):
        self.interactive = stdin_text is None
        self.lines = stdin_text.splitlines() if stdin_text is not None else []
        self.index = 0

    def read(self, prompt):
        if self.interactive:
            return input(prompt)
        if self.index >= len(self.lines):
            raise VMError("No more input available.")
        line = self.lines[self.index]
        self.index += 1
        return line


class BoundMethod:
    """A string method looked up with `text.name`, called later with arguments."""
    def __init__(self, obj, method_name):
        self.obj, self.method_name = obj, method_name

    def __call__(self, args):
        s, name = self.obj, self.method_name
        if name == "upper": return s.upper()
        if name == "lower": return s.lower()
        if name == "trim": return s.strip()
        if name == "contains":
            if not args: raise VMError("contains() requires one argument.")
            return args[0] in s
        if name == "split": return s.split(args[0] if args else " ")
        if name == "replace":
            if len(args) != 2: raise VMError("replace() requires two arguments.")
            return s.replace(args[0], args[1])
        raise VMError(f"String has no method named '{name}'.")


# ---- built-in functions (same behaviour and messages as the AST interpreter) ----
def _len(args):
    if len(args) != 1: raise VMError("len() takes exactly one argument.")
    if isinstance(args[0], (list, str, dict)): return len(args[0])
    raise VMError("len() only works on arrays, strings, and objects.")

def _push(args):
    if len(args) != 2: raise VMError("push() takes two arguments: an array and an item.")
    if not isinstance(args[0], list): raise VMError("First argument to push() must be an array.")
    args[0].append(args[1])

def _pop(args):
    if len(args) != 1: raise VMError("pop() takes exactly one argument.")
    if not isinstance(args[0], list): raise VMError("Argument to pop() must be an array.")
    if not args[0]: raise VMError("Cannot pop from an empty array.")
    return args[0].pop()

def _read_file(args):
    if len(args) != 1 or not isinstance(args[0], str): raise VMError("read_file() takes one string argument: a filepath.")
    try:
        with open(args[0], 'r', encoding='utf-8') as f: return f.read()
    except FileNotFoundError: raise VMError(f"File not found: '{args[0]}'")
    except Exception as e: raise VMError(f"Error reading file '{args[0]}': {e}")

def _write_file(args):
    if len(args) != 2 or not isinstance(args[0], str): raise VMError("write_file() takes two arguments: a filepath and content.")
    try:
        with open(args[0], 'w', encoding='utf-8') as f: f.write(str(args[1]))
    except Exception as e: raise VMError(f"Error writing to file '{args[0]}': {e}")

BUILTINS = {
    "sqrt": lambda args: math.sqrt(args[0]),
    "pow": lambda args: math.pow(args[0], args[1]),
    "max": lambda args: max(args[0] if len(args) == 1 and isinstance(args[0], list) else args),
    "min": lambda args: min(args[0] if len(args) == 1 and isinstance(args[0], list) else args),
    "round": lambda args: round(args[0], args[1] if len(args) > 1 else 0),
    "len": _len, "push": _push, "pop": _pop,
    "read_file": _read_file, "write_file": _write_file,
}


class VM:
    def __init__(self, script, stdin_text=None, input_state=None, module_cache=None):
        script = Closure(script)
        self.stack = [script]  # slot 0 of the script frame holds the script itself
        self.frames = [CallFrame(script, 0)]
        self.open_upvalues = {}  # stack slot -> open Upvalue pointing at it
        self.handlers = []
        self.globals = {}
        self.const_globals = set()
        self.input = input_state or InputState(stdin_text)
        self.module_cache = module_cache if module_cache is not None else {}
        for name, fn in BUILTINS.items():
            self.globals[name] = NativeFunction(name, fn)
            self.const_globals.add(name)

    def run(self):
        _ACTIVE_VMS.append(self)
        try:
            self._run_frames(0)
        finally:
            _ACTIVE_VMS.pop()

    def call_method(self, receiver, closure, args):
        """Call a BranLang method from Python (operator overloading, __str__)."""
        if len(args) != closure.function.arity:
            raise VMError(f"Expected {closure.function.arity} arguments but got {len(args)}.")
        if len(self.frames) >= MAX_FRAMES:
            raise VMError("Maximum recursion depth exceeded.")
        base = len(self.stack)
        self.stack.append(receiver)
        self.stack.extend(args)
        stop_depth = len(self.frames)
        self.frames.append(CallFrame(closure, base))
        return self._run_frames(stop_depth)

    def _run_frames(self, stop_depth):
        """Execute until the frame count drops back to stop_depth (0: until HALT),
        sending errors to try handlers opened above stop_depth."""
        while True:
            try:
                return self._execute(stop_depth)
            except BranError as e:
                if not self.handlers or self.handlers[-1].frame_count <= stop_depth:
                    raise
                # Unwind to the innermost try block and jump to its catch handler.
                handler = self.handlers.pop()
                del self.frames[handler.frame_count:]
                self._close_upvalues(handler.stack_len)
                del self.stack[handler.stack_len:]
                self.stack.append(str(e))
                self.frames[-1].ip = handler.handler_ip

    def _execute(self, stop_depth=0):
        # Opcodes as plain-int locals: much faster to compare than IntEnum members.
        (ADD, AND, ASK, BUILD_LIST, BUILD_MAP, CALL, COALESCE, CONST, DEFINE_CONST,
        DEFINE_GLOBAL, DIV, EQ, FALSE, FOR_ITER, GET_GLOBAL, GET_INDEX, GET_ITER, GET_LOCAL,
        GT, GTE, HALT, IMPORT, JUMP, JUMP_IF_FALSE, LOOP, LT, LTE, MOD, MUL, NE, NEGATE, NULL,
        OR, POP, POP_TRY, POW, PRINT_N, RAISE, RANGE_COND, RETURN, SETUP_TRY, SET_GLOBAL,
        SET_INDEX, SET_LOCAL, SUB, TRUE, CLOSURE, GET_UPVALUE, SET_UPVALUE,
        CLOSE_UPVALUE, CLOSE_FROM, CLASS, INHERIT, METHOD, GET_SUPER) = _OPCODE_VALUES
        stack, frames, globals_ = self.stack, self.frames, self.globals
        frame = frames[-1]
        code, constants = frame.function.chunk.code, frame.function.chunk.constants
        base, ip = frame.base, frame.ip
        upvalues = frame.closure.upvalues
        open_upvalues = self.open_upvalues

        while True:
            op = code[ip]
            ip += 1

            if op == CONST:
                stack.append(constants[(code[ip] << 8) | code[ip + 1]]); ip += 2
            elif op == GET_LOCAL:
                stack.append(stack[base + code[ip]]); ip += 1
            elif op == SET_LOCAL:
                stack[base + code[ip]] = stack[-1]; ip += 1
            elif op == GET_GLOBAL:
                name = constants[(code[ip] << 8) | code[ip + 1]]; ip += 2
                if name not in globals_:
                    raise VMError(f"Undefined variable '{name}'.")
                stack.append(globals_[name])
            elif op == SET_GLOBAL:
                name = constants[(code[ip] << 8) | code[ip + 1]]; ip += 2
                if name not in globals_:
                    raise VMError(f"Undefined variable '{name}'.")
                if name in self.const_globals:
                    raise VMError(f"Cannot assign to constant '{name}'.")
                globals_[name] = stack[-1]
            elif op == DEFINE_GLOBAL or op == DEFINE_CONST:
                name = constants[(code[ip] << 8) | code[ip + 1]]; ip += 2
                globals_[name] = stack.pop()
                if op == DEFINE_CONST: self.const_globals.add(name)
                else: self.const_globals.discard(name)
            elif op == POP:
                stack.pop()
            elif op == NULL: stack.append(None)
            elif op == TRUE: stack.append(True)
            elif op == FALSE: stack.append(False)

            elif op == JUMP:
                ip += 2 + ((code[ip] << 8) | code[ip + 1])
            elif op == JUMP_IF_FALSE:
                offset = (code[ip] << 8) | code[ip + 1]; ip += 2
                if not stack[-1]: ip += offset
            elif op == LOOP:
                ip += 2 - ((code[ip] << 8) | code[ip + 1])
            elif op == RANGE_COND:
                step = stack.pop(); end = stack.pop(); i = stack.pop()
                stack.append((step > 0 and i <= end) or (step < 0 and i >= end))
            elif op == GET_ITER:
                obj = stack[-1]
                if isinstance(obj, list): stack[-1] = iter(obj)
                elif isinstance(obj, dict): stack[-1] = iter(obj.keys())
                else: raise VMError("ForEach only works on arrays and objects.")
            elif op == FOR_ITER:
                offset = (code[ip] << 8) | code[ip + 1]; ip += 2
                try:
                    stack.append(next(stack[-1]))
                except StopIteration:
                    ip += offset

            elif op == CALL:
                call_ip = ip - 1
                argc = code[ip]; ip += 1
                callee = stack[-1 - argc]
                if callee.__class__ is not Closure:
                    if isinstance(callee, (NativeFunction, BoundMethod)):
                        args = stack[len(stack) - argc:]
                        del stack[len(stack) - argc - 1:]
                        stack.append(callee(args))
                        continue
                    if isinstance(callee, ObjBoundMethod):
                        stack[-1 - argc] = callee.receiver
                        callee = callee.method
                    elif isinstance(callee, ObjClass):
                        stack[-1 - argc] = ObjInstance(callee)
                        init = callee.methods.get('init')
                        if init is None:
                            if argc:
                                raise VMError(f"Expected 0 arguments but got {argc}.")
                            continue
                        callee = init
                    else:
                        name = frame.function.chunk.call_names.get(call_ip, 'expression')
                        raise VMError(f"'{name}' is not a callable function.")
                if argc != callee.function.arity:
                    raise VMError(f"Expected {callee.function.arity} arguments but got {argc}.")
                if len(frames) >= MAX_FRAMES:
                    raise VMError("Maximum recursion depth exceeded.")
                frame.ip = ip
                frame = CallFrame(callee, len(stack) - argc - 1)
                frames.append(frame)
                ip = 0
                chunk = callee.function.chunk
                code, constants, base, upvalues = chunk.code, chunk.constants, frame.base, callee.upvalues
            elif op == RETURN:
                result = stack.pop()
                frames.pop()
                if open_upvalues:
                    self._close_upvalues(frame.base)
                del stack[frame.base:]
                stack.append(result)
                # Drop try handlers that belonged to the frame we just left.
                while self.handlers and self.handlers[-1].frame_count > len(frames):
                    self.handlers.pop()
                if len(frames) == stop_depth:
                    return stack.pop()
                frame = frames[-1]
                code, constants, base, ip = frame.function.chunk.code, frame.function.chunk.constants, frame.base, frame.ip
                upvalues = frame.closure.upvalues

            elif op == ADD:
                b = stack.pop(); a = stack.pop()
                stack.append(str(a) + str(b) if isinstance(a, str) or isinstance(b, str) else a + b)
            elif op == SUB:
                b = stack.pop(); stack[-1] = stack[-1] - b
            elif op == MUL:
                b = stack.pop(); stack[-1] = stack[-1] * b
            elif op == DIV:
                b = stack.pop()
                if b.__class__ in (int, float, bool) and b == 0: raise VMError("Division by zero.")
                stack[-1] = stack[-1] / b
            elif op == MOD:
                b = stack.pop(); stack[-1] = stack[-1] % b
            elif op == POW:
                b = stack.pop(); stack[-1] = stack[-1] ** b
            elif op == EQ:
                b = stack.pop(); stack[-1] = stack[-1] == b
            elif op == NE:
                b = stack.pop(); stack[-1] = stack[-1] != b
            elif op == LT:
                b = stack.pop(); stack[-1] = stack[-1] < b
            elif op == GT:
                b = stack.pop(); stack[-1] = stack[-1] > b
            elif op == LTE:
                b = stack.pop(); stack[-1] = stack[-1] <= b
            elif op == GTE:
                b = stack.pop(); stack[-1] = stack[-1] >= b
            elif op == AND:
                b = stack.pop(); stack[-1] = bool(stack[-1] and b)
            elif op == OR:
                b = stack.pop(); stack[-1] = bool(stack[-1] or b)
            elif op == COALESCE:
                b = stack.pop()
                if stack[-1] is None: stack[-1] = b
            elif op == NEGATE:
                stack[-1] = -stack[-1]

            elif op == GET_UPVALUE:
                up = upvalues[code[ip]]; ip += 1
                stack.append(stack[up.slot] if up.is_open else up.value)
            elif op == SET_UPVALUE:
                up = upvalues[code[ip]]; ip += 1
                if up.is_open: stack[up.slot] = stack[-1]
                else: up.value = stack[-1]
            elif op == CLOSURE:
                function = constants[(code[ip] << 8) | code[ip + 1]]; ip += 2
                captured = []
                for _ in range(function.upvalue_count):
                    is_local, index = code[ip], code[ip + 1]; ip += 2
                    captured.append(self._capture_upvalue(base + index) if is_local else upvalues[index])
                stack.append(Closure(function, captured))
            elif op == CLOSE_UPVALUE:
                self._close_upvalues(len(stack) - 1)
                stack.pop()
            elif op == CLOSE_FROM:
                slot = code[ip]; ip += 1
                if open_upvalues: self._close_upvalues(base + slot)
            elif op == BUILD_LIST:
                count = (code[ip] << 8) | code[ip + 1]; ip += 2
                items = stack[len(stack) - count:]
                del stack[len(stack) - count:]
                stack.append(items)
            elif op == BUILD_MAP:
                count = (code[ip] << 8) | code[ip + 1]; ip += 2
                items = stack[len(stack) - 2 * count:]
                del stack[len(stack) - 2 * count:]
                stack.append({items[i]: items[i + 1] for i in range(0, len(items), 2)})
            elif op == GET_INDEX:
                key = stack.pop(); obj = stack.pop()
                stack.append(self._get_member(obj, key, frame.function.in_class))
            elif op == SET_INDEX:
                value = stack.pop(); key = stack.pop(); obj = stack.pop()
                self._set_member(obj, key, value, frame.function.in_class)
                stack.append(value)
            elif op == CLASS:
                stack.append(ObjClass(constants[(code[ip] << 8) | code[ip + 1]])); ip += 2
            elif op == INHERIT:
                klass = stack.pop(); superclass = stack[-1]
                if not isinstance(superclass, ObjClass):
                    raise VMError(f"Class '{klass.name}' can only inherit from a class.")
                klass.methods.update(superclass.methods)
                klass.superclass = superclass
            elif op == METHOD:
                name = constants[(code[ip] << 8) | code[ip + 1]]; ip += 2
                method = stack.pop()
                stack[-1].methods[name] = method
            elif op == GET_SUPER:
                name = constants[(code[ip] << 8) | code[ip + 1]]; ip += 2
                superclass = stack.pop(); instance = stack.pop()
                method = superclass.methods.get(name)
                if method is None:
                    raise VMError(f"Superclass '{superclass.name}' has no method '{name}'.")
                stack.append(ObjBoundMethod(instance, method))

            elif op == PRINT_N:
                count = code[ip]; ip += 1
                values = stack[len(stack) - count:]
                del stack[len(stack) - count:]
                print(*values)
            elif op == ASK:
                kind = code[ip]; ip += 1
                stack.append(self._ask(stack.pop(), kind))
            elif op == IMPORT:
                filename = constants[(code[ip] << 8) | code[ip + 1]]; ip += 2
                self._import(filename)

            elif op == SETUP_TRY:
                offset = (code[ip] << 8) | code[ip + 1]; ip += 2
                self.handlers.append(TryHandler(len(frames), len(stack), ip + offset))
            elif op == POP_TRY:
                self.handlers.pop()
            elif op == RAISE:
                raise VMError(str(stack.pop()))
            elif op == HALT:
                return
            else:
                raise VMError(f"Unknown opcode {op}")

    # ---- helpers -----------------------------------------------------
    def _capture_upvalue(self, slot):
        up = self.open_upvalues.get(slot)
        if up is None:
            up = self.open_upvalues[slot] = Upvalue(slot)
        return up

    def _close_upvalues(self, from_slot):
        """Move captured values at stack slots >= from_slot into their upvalues."""
        for slot in [s for s in self.open_upvalues if s >= from_slot]:
            up = self.open_upvalues.pop(slot)
            up.value, up.is_open = self.stack[slot], False

    @staticmethod
    def _get_member(obj, key, in_class):
        if isinstance(obj, ObjInstance):
            if not isinstance(key, str): raise VMError("Property name must be a string.")
            if not in_class and _is_private(key):
                raise VMError(f"Cannot access private property '{key}' outside of a class.")
            if key in obj.fields: return obj.fields[key]
            method = obj.klass.methods.get(key)
            if method is not None: return ObjBoundMethod(obj, method)
            raise VMError(f"'{obj.klass.name}' instance has no property '{key}'.")
        if isinstance(obj, list):
            if not isinstance(key, int): raise VMError("Array index must be an integer.")
            if not (0 <= key < len(obj)): raise VMError(f"Array index out of bounds: {key}")
            return obj[key]
        if isinstance(obj, dict):
            if not isinstance(key, str): raise VMError("Object key must be a string.")
            return obj.get(key)
        if isinstance(obj, str):
            return BoundMethod(obj, key)
        if isinstance(obj, ObjClass):
            raise VMError(f"Use 'new {obj.name}(...)' to create an instance before accessing '{key}'.")
        raise VMError("Can only access members of arrays, objects, strings and class instances.")

    @staticmethod
    def _set_member(obj, key, value, in_class):
        if isinstance(obj, ObjInstance):
            if not isinstance(key, str): raise VMError("Property name must be a string.")
            if not in_class and _is_private(key):
                raise VMError(f"Cannot access private property '{key}' outside of a class.")
            obj.fields[key] = value
        elif isinstance(obj, dict):
            if not isinstance(key, str): raise VMError("Object key must be a string.")
            obj[key] = value
        elif isinstance(obj, list):
            if not isinstance(key, int): raise VMError("Array index must be an integer.")
            if not (0 <= key < len(obj)): raise VMError(f"Array index out of bounds: {key}")
            obj[key] = value
        else:
            raise VMError("Can only assign to members of arrays, objects and class instances.")

    def _ask(self, prompt, kind):
        text = self.input.read(prompt if prompt is not None else "")
        try:
            if kind == 1: return int(text)
            if kind == 2: return float(text)
            return text
        except ValueError:
            type_name = {1: 'int', 2: 'float'}.get(kind, 'string')
            raise VMError(f"Invalid {type_name} input: '{text}'")

    def _import(self, filename):
        exports = self.module_cache.get(filename)
        if exports is None:
            from lexer import Lexer
            from parser_ast import Parser
            try:
                with open(filename, 'r', encoding='utf-8') as f: source = f.read()
            except FileNotFoundError:
                raise VMError(f"Module not found: '{filename}'")
            script = Compiler().compile(Parser(Lexer(source).get_tokens()).parse())
            module_vm = VM(script, input_state=self.input, module_cache=self.module_cache)
            module_vm.run()
            exports = (module_vm.globals, module_vm.const_globals)
            self.module_cache[filename] = exports
        module_globals, module_consts = exports
        for name, value in module_globals.items():
            self.globals[name] = value
            if name in module_consts: self.const_globals.add(name)
            else: self.const_globals.discard(name)
