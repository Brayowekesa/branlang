# compiler.py - compiles the BranLang AST into bytecode for the VM
from parser_ast import *
from lexer import TokenType
from common import CompileError
from bytecode import Op, ObjFunction, ASK_KINDS

BINARY_OPS = {
    TokenType.PLUS: Op.ADD, TokenType.MINUS: Op.SUB, TokenType.MUL: Op.MUL,
    TokenType.DIV: Op.DIV, TokenType.MOD: Op.MOD, TokenType.POW: Op.POW,
    TokenType.EQ: Op.EQ, TokenType.NE: Op.NE, TokenType.LT: Op.LT, TokenType.GT: Op.GT,
    TokenType.LTE: Op.LTE, TokenType.GTE: Op.GTE,
    # Like the AST interpreter, &&, || and ?? evaluate both operands.
    TokenType.AND: Op.AND, TokenType.OR: Op.OR, TokenType.NULL_COALESCE: Op.COALESCE,
}

# Nodes that leave nothing on the stack; any other statement is an expression
# whose value is popped.
STATEMENT_NODES = (VarDecl, ConstDecl, Show, When, Loop, For, ForEach, FnDef, Return,
                   BreakNode, ContinueNode, ImportNode, TryCatch, Block)

MAX_LOCALS = 256
MAX_U16 = 0xFFFF


class Local:
    def __init__(self, name, depth, is_const=False):
        self.name, self.depth, self.is_const = name, depth, is_const
        self.captured = False  # set when a nested function closes over this local


class UpvalueRef:
    def __init__(self, index, is_local, is_const):
        # is_local: `index` is a local slot of the enclosing function;
        # otherwise it is an index into the enclosing function's own upvalues.
        self.index, self.is_local, self.is_const = index, is_local, is_const


class LoopContext:
    def __init__(self, locals_count, try_depth, continue_target=None):
        self.locals_count = locals_count      # locals that exist outside the loop body
        self.try_depth = try_depth            # try blocks open outside the loop
        self.continue_target = continue_target  # backward target, or None to patch forward
        self.break_jumps = []
        self.continue_jumps = []


class Compiler:
    def __init__(self, name="<script>", arity=0, enclosing=None):
        self.function = ObjFunction(name, arity)
        self.enclosing = enclosing
        self.is_script = enclosing is None
        self.scope_depth = 0 if self.is_script else 1
        # Slot 0 holds the function being executed (the callee).
        self.locals = [Local("", self.scope_depth)]
        self.upvalues = []
        self.loops = []
        self.try_depth = 0

    # ---- entry point -------------------------------------------------
    def compile(self, node):
        self.visit(node)
        self.emit(Op.HALT)
        return self.function

    # ---- emit helpers ------------------------------------------------
    @property
    def chunk(self):
        return self.function.chunk

    def emit(self, *data):
        for byte in data:
            self.chunk.write(byte)

    def emit_u16(self, op, value):
        if value > MAX_U16:
            raise CompileError("Too many constants or items in one function.")
        self.emit(op, (value >> 8) & 0xFF, value & 0xFF)

    def emit_constant(self, value):
        self.emit_u16(Op.CONST, self.chunk.add_constant(value))

    def name_constant(self, name):
        return self.chunk.add_constant(name)

    def emit_jump(self, op):
        self.emit(op, 0xFF, 0xFF)
        return len(self.chunk.code) - 2

    def patch_jump(self, offset):
        jump = len(self.chunk.code) - offset - 2
        if jump > MAX_U16:
            raise CompileError("Too much code to jump over.")
        self.chunk.code[offset] = (jump >> 8) & 0xFF
        self.chunk.code[offset + 1] = jump & 0xFF

    def emit_loop(self, loop_start):
        offset = len(self.chunk.code) - loop_start + 3
        if offset > MAX_U16:
            raise CompileError("Loop body too large.")
        self.emit_u16(Op.LOOP, offset)

    def emit_raise(self, message):
        self.emit_constant(message)
        self.emit(Op.RAISE)

    # ---- scopes and locals -------------------------------------------
    def begin_scope(self):
        self.scope_depth += 1

    def end_scope(self):
        self.scope_depth -= 1
        while self.locals and self.locals[-1].depth > self.scope_depth:
            self.emit(Op.CLOSE_UPVALUE if self.locals[-1].captured else Op.POP)
            self.locals.pop()

    def add_local(self, name, is_const=False):
        if len(self.locals) >= MAX_LOCALS:
            raise CompileError("Too many local variables in one function.")
        self.locals.append(Local(name, self.scope_depth, is_const))
        return len(self.locals) - 1

    def resolve_local(self, name):
        for i in range(len(self.locals) - 1, 0, -1):
            if self.locals[i].name == name:
                return i
        return -1

    def resolve_upvalue(self, name):
        """Find `name` in an enclosing function's locals (capturing it) or upvalues."""
        if self.enclosing is None:
            return -1
        slot = self.enclosing.resolve_local(name)
        if slot != -1:
            local = self.enclosing.locals[slot]
            local.captured = True
            return self.add_upvalue(slot, True, local.is_const)
        index = self.enclosing.resolve_upvalue(name)
        if index != -1:
            return self.add_upvalue(index, False, self.enclosing.upvalues[index].is_const)
        return -1

    def add_upvalue(self, index, is_local, is_const):
        for i, up in enumerate(self.upvalues):
            if up.index == index and up.is_local == is_local:
                return i
        if len(self.upvalues) >= 256:
            raise CompileError("Too many captured variables in one function.")
        self.upvalues.append(UpvalueRef(index, is_local, is_const))
        self.function.upvalue_count = len(self.upvalues)
        return len(self.upvalues) - 1

    def declare_variable(self, name, is_const=False):
        """Bind the value on top of the stack to `name` in the current scope."""
        if self.scope_depth == 0:
            op = Op.DEFINE_CONST if is_const else Op.DEFINE_GLOBAL
            self.emit_u16(op, self.name_constant(name))
            return
        # Re-declaring in the same scope overwrites, as in the interpreter.
        slot = self.find_in_current_scope(name)
        if slot != -1:
            self.locals[slot].is_const = is_const
            self.emit(Op.SET_LOCAL, slot, Op.POP)
        else:
            self.add_local(name, is_const)

    def find_in_current_scope(self, name):
        for i in range(len(self.locals) - 1, 0, -1):
            local = self.locals[i]
            if local.depth < self.scope_depth:
                break
            if local.name == name:
                return i
        return -1

    # ---- dispatch ----------------------------------------------------
    def visit(self, node):
        visitor = getattr(self, f'visit_{type(node).__name__}', None)
        if visitor is None:
            raise CompileError(f"The VM cannot compile {type(node).__name__} yet.")
        visitor(node)

    def statement(self, node):
        self.visit(node)
        if not isinstance(node, STATEMENT_NODES):
            self.emit(Op.POP)

    def visit_Block(self, node):
        for stmt in node.statements:
            self.statement(stmt)

    def scoped_block(self, node):
        self.begin_scope()
        self.visit(node)
        self.end_scope()

    # ---- literals and expressions -----------------------------------
    def visit_Number(self, node): self.emit_constant(node.value)
    def visit_String(self, node): self.emit_constant(node.value)
    def visit_Boolean(self, node): self.emit(Op.TRUE if node.value else Op.FALSE)
    def visit_NullNode(self, node): self.emit(Op.NULL)

    def visit_BinOp(self, node):
        self.visit(node.left)
        self.visit(node.right)
        op = BINARY_OPS.get(node.op.type)
        if op is None:
            raise CompileError(f"Unknown binary operator {node.op.type.name}")
        self.emit(op)

    def visit_UnaryOp(self, node):
        self.visit(node.expr)
        if node.op.type == TokenType.MINUS:
            self.emit(Op.NEGATE)

    def visit_ArrayLiteral(self, node):
        for element in node.elements:
            self.visit(element)
        self.emit_u16(Op.BUILD_LIST, len(node.elements))

    def visit_ObjectLiteral(self, node):
        for key, value in node.pairs.items():
            self.emit_constant(key)
            self.visit(value)
        self.emit_u16(Op.BUILD_MAP, len(node.pairs))

    def visit_MemberAccess(self, node):
        self.visit(node.callee)
        self.visit(node.member)
        self.emit(Op.GET_INDEX)

    visit_IndexAccess = visit_MemberAccess

    def visit_MemberAssign(self, node):
        self.visit(node.callee)
        self.visit(node.member)
        self.visit(node.value)
        self.emit(Op.SET_INDEX)

    def visit_Ask(self, node):
        self.visit(node.prompt)
        self.emit(Op.ASK, ASK_KINDS[node.numeric_type])

    # ---- variables ---------------------------------------------------
    def visit_VarDecl(self, node):
        self.visit(node.expr)
        self.declare_variable(node.name_node.name)

    def visit_ConstDecl(self, node):
        self.visit(node.expr)
        self.declare_variable(node.name_node.name, is_const=True)

    def visit_VarAccess(self, node):
        slot = self.resolve_local(node.name)
        if slot != -1:
            self.emit(Op.GET_LOCAL, slot)
            return
        index = self.resolve_upvalue(node.name)
        if index != -1:
            self.emit(Op.GET_UPVALUE, index)
        else:
            self.emit_u16(Op.GET_GLOBAL, self.name_constant(node.name))

    def visit_VarAssign(self, node):
        name = node.name_node.name
        self.visit(node.expr)
        slot = self.resolve_local(name)
        index = self.resolve_upvalue(name) if slot == -1 else -1
        is_const = ((slot != -1 and self.locals[slot].is_const) or
                    (index != -1 and self.upvalues[index].is_const))
        if is_const:
            self.emit(Op.POP)
            self.emit_raise(f"Cannot assign to constant '{name}'.")
            self.emit(Op.NULL)  # keeps the stack balanced; never reached
        elif slot != -1:
            self.emit(Op.SET_LOCAL, slot)
        elif index != -1:
            self.emit(Op.SET_UPVALUE, index)
        else:
            self.emit_u16(Op.SET_GLOBAL, self.name_constant(name))

    # ---- statements --------------------------------------------------
    def visit_Show(self, node):
        if len(node.expressions) > 255:
            raise CompileError("show() takes at most 255 values.")
        for expr in node.expressions:
            self.visit(expr)
        self.emit(Op.PRINT_N, len(node.expressions))

    def visit_When(self, node):
        self.visit(node.condition)
        then_jump = self.emit_jump(Op.JUMP_IF_FALSE)
        self.emit(Op.POP)
        self.scoped_block(node.true_block)
        else_jump = self.emit_jump(Op.JUMP)
        self.patch_jump(then_jump)
        self.emit(Op.POP)
        if node.false_block is not None:
            if isinstance(node.false_block, When):
                self.visit(node.false_block)  # 'otherwise when' chain
            else:
                self.scoped_block(node.false_block)
        self.patch_jump(else_jump)

    def loop_body(self, body, ctx):
        self.loops.append(ctx)
        self.scoped_block(body)
        self.loops.pop()

    def visit_Loop(self, node):
        loop_start = len(self.chunk.code)
        self.visit(node.condition)
        exit_jump = self.emit_jump(Op.JUMP_IF_FALSE)
        self.emit(Op.POP)
        ctx = LoopContext(len(self.locals), self.try_depth, continue_target=loop_start)
        self.loop_body(node.body, ctx)
        self.emit_loop(loop_start)
        self.patch_jump(exit_jump)
        self.emit(Op.POP)
        for jump in ctx.break_jumps:
            self.patch_jump(jump)

    def visit_For(self, node):
        # Hidden locals hold the counter, end and step, each evaluated once.
        # The loop variable is a fresh copy of the counter each iteration, so
        # assigning to it in the body doesn't change the iteration (as in the interpreter).
        self.begin_scope()
        self.visit(node.start); counter = self.add_local(" counter")
        self.visit(node.end); end = self.add_local(" end")
        self.visit(node.step); step = self.add_local(" step")

        loop_start = len(self.chunk.code)
        self.emit(Op.GET_LOCAL, counter, Op.GET_LOCAL, end, Op.GET_LOCAL, step, Op.RANGE_COND)
        exit_jump = self.emit_jump(Op.JUMP_IF_FALSE)
        self.emit(Op.POP)

        ctx = LoopContext(len(self.locals), self.try_depth)
        self.loops.append(ctx)
        self.begin_scope()
        self.emit(Op.GET_LOCAL, counter)
        self.add_local(node.var_name_node.name)
        self.visit(node.body)
        self.end_scope()
        self.loops.pop()

        for jump in ctx.continue_jumps:
            self.patch_jump(jump)
        self.emit(Op.GET_LOCAL, counter, Op.GET_LOCAL, step, Op.ADD, Op.SET_LOCAL, counter, Op.POP)
        self.emit_loop(loop_start)

        self.patch_jump(exit_jump)
        self.emit(Op.POP)
        for jump in ctx.break_jumps:
            self.patch_jump(jump)
        self.end_scope()

    def visit_ForEach(self, node):
        self.begin_scope()
        self.visit(node.iterable)
        self.emit(Op.GET_ITER)
        self.add_local(" iter")

        loop_start = len(self.chunk.code)
        exit_jump = self.emit_jump(Op.FOR_ITER)  # pushes the next item, or jumps when done

        ctx = LoopContext(len(self.locals), self.try_depth, continue_target=loop_start)
        self.loops.append(ctx)
        self.begin_scope()
        self.add_local(node.var_name_node.name)
        self.visit(node.body)
        self.end_scope()
        self.loops.pop()

        self.emit_loop(loop_start)
        self.patch_jump(exit_jump)
        for jump in ctx.break_jumps:
            self.patch_jump(jump)
        self.end_scope()  # pops the iterator

    def unwind_to_loop(self, ctx):
        """Pop the body's locals and close try blocks before break/continue jumps."""
        for _ in range(self.try_depth - ctx.try_depth):
            self.emit(Op.POP_TRY)
        count = len(self.locals) - ctx.locals_count
        if count:
            # A closure later in the body may capture one of these locals (not
            # known yet at this point), so close their upvalues before popping.
            self.emit(Op.CLOSE_FROM, ctx.locals_count)
            for _ in range(count):
                self.emit(Op.POP)

    def visit_BreakNode(self, node):
        if not self.loops:
            raise CompileError("'break' used outside of a loop.")
        ctx = self.loops[-1]
        self.unwind_to_loop(ctx)
        ctx.break_jumps.append(self.emit_jump(Op.JUMP))

    def visit_ContinueNode(self, node):
        if not self.loops:
            raise CompileError("'continue' used outside of a loop.")
        ctx = self.loops[-1]
        self.unwind_to_loop(ctx)
        if ctx.continue_target is not None:
            self.emit_loop(ctx.continue_target)
        else:
            ctx.continue_jumps.append(self.emit_jump(Op.JUMP))

    def visit_TryCatch(self, node):
        handler_jump = self.emit_jump(Op.SETUP_TRY)
        self.try_depth += 1
        self.scoped_block(node.try_block)
        self.try_depth -= 1
        self.emit(Op.POP_TRY)
        end_jump = self.emit_jump(Op.JUMP)

        # The VM jumps here with the error message pushed on the stack.
        self.patch_jump(handler_jump)
        self.begin_scope()
        self.add_local(node.error_var_node.name)
        self.visit(node.catch_block)
        self.end_scope()
        self.patch_jump(end_jump)

    def visit_ImportNode(self, node):
        self.emit_u16(Op.IMPORT, self.name_constant(node.filename))

    # ---- functions ---------------------------------------------------
    def visit_FnDef(self, node):
        name = node.name_node.name
        if len(node.params) > 255:
            raise CompileError("A function can take at most 255 parameters.")
        # Declare the local before compiling the body, so a nested function can
        # call itself (recursion) through an upvalue. Globals are found by name.
        redeclared = self.scope_depth > 0 and self.find_in_current_scope(name) != -1
        if self.scope_depth > 0 and not redeclared:
            self.add_local(name)

        fn_compiler = Compiler(name, len(node.params), enclosing=self)
        for param in node.params:
            fn_compiler.add_local(param.name)
        fn_compiler.visit(node.body)
        fn_compiler.emit(Op.NULL, Op.RETURN)  # implicit 'return null'

        self.emit_u16(Op.CLOSURE, self.chunk.add_constant(fn_compiler.function))
        for up in fn_compiler.upvalues:
            self.emit(1 if up.is_local else 0, up.index)

        if self.scope_depth == 0:
            self.emit_u16(Op.DEFINE_GLOBAL, self.name_constant(name))
        elif redeclared:
            self.declare_variable(name)  # overwrite the existing local of the same name

    def visit_FnCall(self, node):
        if len(node.args) > 255:
            raise CompileError("A call can pass at most 255 arguments.")
        self.visit(node.callee)
        for arg in node.args:
            self.visit(arg)
        self.chunk.call_names[len(self.chunk.code)] = getattr(node.callee, 'name', 'expression')
        self.emit(Op.CALL, len(node.args))

    def visit_Return(self, node):
        if self.is_script:
            # The interpreter only fails when the return is actually reached.
            self.emit_raise("Return statement used outside of a function.")
            return
        self.visit(node.expr)
        self.emit(Op.RETURN)
