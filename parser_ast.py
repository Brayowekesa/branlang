# parser_ast.py (Full Updated Version with Object Support)

from lexer import TokenType, Token

class ParserError(Exception):
    pass
class BranError(Exception):
    pass
# --- AST Node Definitions ---
class AST:
    pass

class BinOp(AST):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
# Add this with the other AST node classes
class ImportNode(AST):
    def __init__(self, filename_token):
        self.filename_token = filename_token
        self.filename = filename_token.value

class UnaryOp(AST):
    def __init__(self, op, expr):
        self.op = op
        self.expr = expr

class Number(AST):
    def __init__(self, token):
        self.token = token
        self.value = token.value

class String(AST):
    def __init__(self, token):
        self.token = token
        self.value = token.value

class Boolean(AST):
    def __init__(self, token):
        self.token = token
        self.value = token.type == TokenType.TRUE

class Block(AST):
    def __init__(self, statements):
        self.statements = statements

class VarDecl(AST):
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

class VarAssign(AST):
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

class VarAccess(AST):
    def __init__(self, token):
        self.token = token
        self.name = token.value

class Show(AST):
    def __init__(self, expressions):
        self.expressions = expressions

class When(AST):
    def __init__(self, condition, true_block, false_block):
        self.condition = condition
        self.true_block = true_block
        self.false_block = false_block

class Loop(AST):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

class FnDef(AST):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

class FnCall(AST):
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args

class Return(AST):
    def __init__(self, expr):
        self.expr = expr

class Ask(AST):
    def __init__(self, prompt, numeric_type=None):
        self.prompt = prompt
        self.numeric_type = numeric_type

class ArrayLiteral(AST):
    def __init__(self, elements):
        self.elements = elements

class IndexAccess(AST):
    def __init__(self, callee, index):
        self.callee = callee
        self.index = index

class ObjectLiteral(AST):
    def __init__(self, pairs):
        self.pairs = pairs

class MemberAccess(AST):
    def __init__(self, callee, member):
        self.callee = callee
        self.member = member

class MemberAssign(AST):
    def __init__(self, callee, member, value):
        self.callee = callee
        self.member = member
        self.value = value

class For(AST):
    def __init__(self, var_name, start, end, step, body):
        self.var_name = var_name
        self.start = start
        self.end = end
        self.step = step
        self.body = body

class ForEach(AST):
    def __init__(self, var_name, iterable, body):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body

# --- The Parser ---
class Parser:
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0
        self.current_token = self.tokens[self.pos]

    # Add this method inside the Parser class
    def import_statement(self):
        self.eat(TokenType.IMPORT)
        filename_token = self.current_token
        self.eat(TokenType.STRING)
        return ImportNode(filename_token)

        # Add this new method inside the Parser class
    def skip_layout_tokens(self):
        """Skips over NEWLINE, INDENT, and DEDENT tokens."""
        while self.current_token.type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT):
            self.advance()

    def error(self, message):
        raise ParserError(f"{message} (at {self.current_token})")

    def advance(self):
        self.pos += 1
        self.current_token = self.tokens[self.pos]

    def eat(self, token_type):
        if self.current_token.type == token_type:
            self.advance()
        else:
            self.error(f"Expected token {token_type.name}, but got {self.current_token.type.name}")

    # In class Parserss
    def skip_newlines(self):
        while self.current_token.type == TokenType.NEWLINE:
            self.advance()

    def parse(self):
        return self.program()

        # In class Parser
    def program(self):
        statements = []
        self.skip_newlines() # Use the simpler helper
        while self.current_token.type != TokenType.EOF:
            statements.append(self.statement())
            self.skip_newlines()
        return Block(statements)

    # In class Parser
    def block(self):
        self.eat(TokenType.COLON)
        self.eat(TokenType.NEWLINE)
        if self.current_token.type != TokenType.INDENT:
            self.error("Expected an indented block.")
        self.eat(TokenType.INDENT)

        statements = []
        # The program's main loop will skip newlines after each statement
        while self.current_token.type != TokenType.DEDENT and self.current_token.type != TokenType.EOF:
            statements.append(self.statement())
            # We must skip newlines here to handle blank lines inside a block
            self.skip_newlines() 
        
        # After the loop, we must be at a DEDENT to close the block
        self.eat(TokenType.DEDENT)
        return Block(statements)

    def statement(self):
        if self.current_token.type == TokenType.MEM:
            return self.mem_declaration()
        if self.current_token.type == TokenType.SHOW:
            return self.show_statement()
        if self.current_token.type == TokenType.WHEN:
            return self.when_statement()
        if self.current_token.type == TokenType.LOOP:
            return self.loop_statement()
        if self.current_token.type == TokenType.FOR:
            return self.for_statement()
        if self.current_token.type == TokenType.IMPORT:
            return self.import_statement()
        if self.current_token.type == TokenType.FN:
            return self.fn_definition()
        if self.current_token.type == TokenType.RETURN:
            self.eat(TokenType.RETURN)
            return Return(self.expression())
        expr = self.expression()
        if isinstance(expr, (VarAssign, MemberAssign, FnCall)):
            return expr
        self.error("Invalid statement. Standalone expressions are not allowed.")

    def mem_declaration(self):
        self.eat(TokenType.MEM)
        name = VarAccess(self.current_token)
        self.eat(TokenType.ID)
        self.eat(TokenType.ASSIGN)
        expr = self.expression()
        return VarDecl(name, expr)

    def show_statement(self):
        self.eat(TokenType.SHOW)
        self.eat(TokenType.LPAREN)
        expressions = []
        self.parse_argument_list(expressions)
        self.eat(TokenType.RPAREN)
        return Show(expressions)

    def when_statement(self):
        self.eat(TokenType.WHEN)
        condition = self.expression()
        true_block = self.block()
        false_block = None
        if self.current_token.type == TokenType.OTHERWISE:
            self.advance()
            if self.current_token.type == TokenType.WHEN:
                false_block = self.when_statement()
            else:
                false_block = self.block()
        return When(condition, true_block, false_block)

    def loop_statement(self):
        self.eat(TokenType.LOOP)
        self.eat(TokenType.LPAREN)
        condition = self.expression()
        self.eat(TokenType.RPAREN)
        body = self.block()
        return Loop(condition, body)

    def for_statement(self):
        self.eat(TokenType.FOR)
        var_name = VarAccess(self.current_token)
        self.eat(TokenType.ID)

        if self.current_token.type == TokenType.IN:
            self.eat(TokenType.IN)
            iterable = self.expression()
            body = self.block()
            return ForEach(var_name, iterable, body)

        elif self.current_token.type == TokenType.FROM:
            self.eat(TokenType.FROM)
            start = self.expression()
            self.eat(TokenType.TO)
            end = self.expression()
            step = Number(Token(TokenType.NUMBER, 1))
            if self.current_token.type == TokenType.STEP:
                self.eat(TokenType.STEP)
                step = self.expression()
            body = self.block()
            return For(var_name, start, end, step, body)

        else:
            self.error("Expected 'in' or 'from' after for loop variable.")

    def fn_definition(self):
        self.eat(TokenType.FN)
        name = VarAccess(self.current_token)
        self.eat(TokenType.ID)
        self.eat(TokenType.LPAREN)
        params = []
        if self.current_token.type == TokenType.ID:
            params.append(VarAccess(self.current_token))
            self.eat(TokenType.ID)
            while self.current_token.type == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                params.append(VarAccess(self.current_token))
                self.eat(TokenType.ID)
        self.eat(TokenType.RPAREN)
        body = self.block()
        return FnDef(name, params, body)

    def parse_argument_list(self, arg_list):
        if self.current_token.type != TokenType.RPAREN:
            arg_list.append(self.expression())
            while self.current_token.type == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                arg_list.append(self.expression())

    def expression(self):
        return self.assignment()

    def assignment(self):
        left = self.logic_or()
        if self.current_token.type == TokenType.ASSIGN:
            self.eat(TokenType.ASSIGN)
            right = self.assignment()
            if isinstance(left, VarAccess):
                return VarAssign(left, right)
            if isinstance(left, MemberAccess):
                return MemberAssign(left.callee, left.member, right)
            self.error("Invalid assignment target.")
        return left

    def logic_or(self):
        node = self.logic_and()
        while self.current_token.type == TokenType.OR:
            op = self.current_token
            self.eat(op.type)
            node = BinOp(node, op, self.logic_and())
        return node

    def logic_and(self):
        node = self.comparison()
        while self.current_token.type == TokenType.AND:
            op = self.current_token
            self.eat(op.type)
            node = BinOp(node, op, self.comparison())
        return node

    def comparison(self):
        node = self.term()
        ops = (
            TokenType.EQ, TokenType.NE,
            TokenType.LT, TokenType.GT,
            TokenType.LTE, TokenType.GTE
        )
        if self.current_token.type in ops:
            op = self.current_token
            self.eat(op.type)
            node = BinOp(node, op, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.current_token.type in (TokenType.PLUS, TokenType.MINUS):
            op = self.current_token
            self.eat(op.type)
            node = BinOp(node, op, self.factor())
        return node

    def factor(self):
        node = self.power()
        while self.current_token.type in (TokenType.MUL, TokenType.DIV, TokenType.MOD):
            op = self.current_token
            self.eat(op.type)
            node = BinOp(node, op, self.power())
        return node

    def power(self):
        node = self.unary()
        if self.current_token.type == TokenType.POW:
            op = self.current_token
            self.eat(op.type)
            node = BinOp(node, op, self.power())
        return node

    def unary(self):
        if self.current_token.type in (TokenType.PLUS, TokenType.MINUS):
            op = self.current_token
            self.eat(op.type)
            return UnaryOp(op, self.unary())
        return self.call()

    def call(self):
        node = self.primary()
        while True:
            if self.current_token.type == TokenType.LPAREN:
                self.eat(TokenType.LPAREN)
                args = []
                self.parse_argument_list(args)
                self.eat(TokenType.RPAREN)
                node = FnCall(callee=node, args=args)

            elif self.current_token.type == TokenType.LBRACKET:
                self.eat(TokenType.LBRACKET)
                index_expr = self.expression()
                self.eat(TokenType.RBRACKET)
                node = MemberAccess(callee=node, member=index_expr)

            elif self.current_token.type == TokenType.DOT:
                self.eat(TokenType.DOT)
                member_token = self.current_token
                self.eat(TokenType.ID)
                member_as_string_node = String(Token(TokenType.STRING, member_token.value))
                node = MemberAccess(callee=node, member=member_as_string_node)

            else:
                break
        return node

    def primary(self):
        token = self.current_token

        if token.type == TokenType.LBRACE:
            self.eat(TokenType.LBRACE)
            pairs = {}
            self.skip_layout_tokens()  # Use the powerful helper

            if self.current_token.type != TokenType.RBRACE:
                while True:
                    # Expect a key for the pair
                    key_token = self.current_token
                    self.eat(TokenType.STRING)
                    self.eat(TokenType.COLON)
                    value_node = self.expression()
                    pairs[key_token.value] = value_node
                    
                    self.skip_layout_tokens() # Use the helper again

                    # If there's a comma, consume it. The comma is now optional before the '}'.
                    if self.current_token.type == TokenType.COMMA:
                        self.eat(TokenType.COMMA)
                        self.skip_layout_tokens()
                    
                    # After a pair, we must either see the closing brace or another key
                    if self.current_token.type == TokenType.RBRACE:
                        break
                    
                    if self.current_token.type != TokenType.STRING:
                        self.error("Expected a string key or '}' in object literal.")
            
            self.eat(TokenType.RBRACE)
            return ObjectLiteral(pairs)

        # The rest of the method for handling other primary expressions remains the same
        if token.type == TokenType.LBRACKET:
            self.eat(TokenType.LBRACKET)
            elements = []
            if self.current_token.type != TokenType.RBRACKET:
                elements.append(self.expression())
                while self.current_token.type == TokenType.COMMA:
                    self.eat(TokenType.COMMA)
                    elements.append(self.expression())
            self.eat(TokenType.RBRACKET)
            return ArrayLiteral(elements)

        if token.type == TokenType.NUMBER:
            self.advance()
            return Number(token)

        if token.type in (TokenType.TRUE, TokenType.FALSE):
            self.advance()
            return Boolean(token)

        if token.type == TokenType.STRING:
            self.advance()
            return String(token)

        if token.type == TokenType.ID:
            self.advance()
            return VarAccess(token)

        if token.type == TokenType.LPAREN:
            self.eat(TokenType.LPAREN)
            node = self.expression()
            self.eat(TokenType.RPAREN)
            return node

        if token.type in (TokenType.ASK, TokenType.ASKINT, TokenType.ASKFLOAT):
            ask_type = token.type
            self.eat(ask_type)
            self.eat(TokenType.LPAREN)
            if self.current_token.type == TokenType.RPAREN:
                prompt = String(Token(TokenType.STRING, ""))
            else:
                prompt = self.expression()
            self.eat(TokenType.RPAREN)
            num_type = (
                'int' if ask_type == TokenType.ASKINT else
                'float' if ask_type == TokenType.ASKFLOAT else
                None
            )
            return Ask(prompt, numeric_type=num_type)

        self.error(f"Unexpected token in expression: {token.type.name}")