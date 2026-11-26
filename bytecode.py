# bytecode.py - opcodes, chunks and runtime function objects for the BranLang VM
from enum import IntEnum


class Op(IntEnum):
    # Literals / stack
    CONST = 0          # u16 constant index
    NULL = 1
    TRUE = 2
    FALSE = 3
    POP = 4
    # Arithmetic / comparison / logic (pop 2, push 1)
    ADD = 5
    SUB = 6
    MUL = 7
    DIV = 8
    MOD = 9
    POW = 10
    EQ = 11
    NE = 12
    LT = 13
    GT = 14
    LTE = 15
    GTE = 16
    AND = 17
    OR = 18
    COALESCE = 19
    NEGATE = 20
    # Variables
    DEFINE_GLOBAL = 21  # u16 name constant
    DEFINE_CONST = 22   # u16 name constant
    GET_GLOBAL = 23     # u16 name constant
    SET_GLOBAL = 24     # u16 name constant
    GET_LOCAL = 25      # u8 slot
    SET_LOCAL = 26      # u8 slot
    # Control flow
    JUMP = 27           # u16 forward offset
    JUMP_IF_FALSE = 28  # u16 forward offset (does not pop the condition)
    LOOP = 29           # u16 backward offset
    RANGE_COND = 30     # pop i, end, step -> push bool
    GET_ITER = 31
    FOR_ITER = 32       # u16 forward offset to jump to when exhausted
    SETUP_TRY = 33      # u16 forward offset to the catch handler
    POP_TRY = 34
    RAISE = 35          # pop message, raise a runtime error
    # Functions
    CALL = 36           # u8 argument count
    RETURN = 37
    # Data structures
    BUILD_LIST = 38     # u16 item count
    BUILD_MAP = 39      # u16 pair count
    GET_INDEX = 40
    SET_INDEX = 41
    # I/O and modules
    PRINT_N = 42        # u8 value count
    ASK = 43            # u8 kind: 0 = string, 1 = int, 2 = float
    IMPORT = 44         # u16 filename constant
    HALT = 45


# Size in bytes of each opcode's operand (opcodes not listed take none).
OPERAND_SIZE = {
    Op.CONST: 2, Op.DEFINE_GLOBAL: 2, Op.DEFINE_CONST: 2, Op.GET_GLOBAL: 2, Op.SET_GLOBAL: 2,
    Op.GET_LOCAL: 1, Op.SET_LOCAL: 1,
    Op.JUMP: 2, Op.JUMP_IF_FALSE: 2, Op.LOOP: 2, Op.FOR_ITER: 2, Op.SETUP_TRY: 2,
    Op.CALL: 1, Op.BUILD_LIST: 2, Op.BUILD_MAP: 2, Op.PRINT_N: 1, Op.ASK: 1, Op.IMPORT: 2,
}

ASK_KINDS = {None: 0, 'int': 1, 'float': 2}


class Chunk:
    def __init__(self):
        self.code = bytearray()
        self.constants = []
        self._constant_index = {}
        self.call_names = {}  # bytecode offset of a CALL -> callee name, for error messages

    def write(self, byte):
        self.code.append(byte)

    def add_constant(self, value):
        # Key on type as well as value so 1, 1.0 and True stay distinct constants.
        if isinstance(value, (str, int, float, bool)) or value is None:
            key = (type(value), value)
            if key in self._constant_index:
                return self._constant_index[key]
            self._constant_index[key] = len(self.constants)
        self.constants.append(value)
        return len(self.constants) - 1


class ObjFunction:
    def __init__(self, name, arity=0):
        self.name = name
        self.arity = arity
        self.chunk = Chunk()

    def __repr__(self):
        return f"<fn {self.name}>"


class NativeFunction:
    def __init__(self, name, fn):
        self.name, self.fn = name, fn

    def __call__(self, args):
        return self.fn(args)

    def __repr__(self):
        return f"<builtin fn {self.name}>"


def disassemble(function, out=print):
    """Print a human-readable listing of a function's bytecode (and nested functions)."""
    chunk = function.chunk
    out(f"== {function.name} ==")
    code, ip = chunk.code, 0
    nested = []
    while ip < len(code):
        op = Op(code[ip])
        size = OPERAND_SIZE.get(op, 0)
        operand = int.from_bytes(code[ip + 1:ip + 1 + size], 'big') if size else None
        line = f"{ip:04d}  {op.name:<14}"
        if op in (Op.CONST, Op.DEFINE_GLOBAL, Op.DEFINE_CONST, Op.GET_GLOBAL, Op.SET_GLOBAL, Op.IMPORT):
            value = chunk.constants[operand]
            line += f"{operand:>4}  {value!r}"
            if isinstance(value, ObjFunction):
                nested.append(value)
        elif op in (Op.JUMP, Op.JUMP_IF_FALSE, Op.FOR_ITER, Op.SETUP_TRY):
            line += f"{operand:>4}  -> {ip + 1 + size + operand:04d}"
        elif op == Op.LOOP:
            line += f"{operand:>4}  -> {ip + 1 + size - operand:04d}"
        elif size:
            line += f"{operand:>4}"
        out(line.rstrip())
        ip += 1 + size
    for fn in nested:
        out("")
        disassemble(fn, out)
