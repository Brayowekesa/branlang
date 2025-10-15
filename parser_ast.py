# parser_ast.py
from lexer import TokenType, Token
from common import ParserError

class AST: pass
class BinOp(AST):
    def __init__(self, left, op, right): self.left, self.op, self.right = left, op, right
class UnaryOp(AST):
    def __init__(self, op, expr): self.op, self.expr = op, expr
class Number(AST):
    def __init__(self, token): self.token, self.value = token, token.value
class String(AST):
    def __init__(self, token): self.token, self.value = token, token.value
class Boolean(AST):
    def __init__(self, token): self.token, self.value = token, token.type == TokenType.TRUE
class Block(AST): 
    def __init__(self, statements): self.statements = statements
class NullNode(AST):
    def __init__(self, token): self.token = token
class VarDecl(AST): 
    def __init__(self, name_node, expr): self.name_node, self.expr = name_node, expr
class ConstDecl(AST):
    def __init__(self, name_node, expr): self.name_node, self.expr = name_node, expr
class VarAssign(AST):
    def __init__(self, name_node, expr): self.name_node, self.expr = name_node, expr
class VarAccess(AST):
    def __init__(self, token): self.token, self.name = token, token.value
class Show(AST):
    def __init__(self, expressions): self.expressions = expressions
class When(AST):
    def __init__(self, condition, true_block, false_block): self.condition, self.true_block, self.false_block = condition, true_block, false_block
class Loop(AST):
    def __init__(self, condition, body): self.condition, self.body = condition, body
class FnDef(AST):
    def __init__(self, name_node, params, body): self.name_node, self.params, self.body = name_node, params, body
class FnCall(AST):
    def __init__(self, callee, args): self.callee, self.args = callee, args
class Return(AST):
    def __init__(self, expr): self.expr = expr
class Ask(AST): 
    def __init__(self, prompt, numeric_type=None): self.prompt, self.numeric_type = prompt, numeric_type
class ArrayLiteral(AST): 
    def __init__(self, elements): self.elements = elements
class IndexAccess(AST): 
    def __init__(self, callee, index): self.callee, self.index = callee, index
class ObjectLiteral(AST): 
    def __init__(self, pairs): self.pairs = pairs
class MemberAccess(AST): 
    def __init__(self, callee, member): self.callee, self.member = callee, member
class MemberAssign(AST): 
    def __init__(self, callee, member, value): self.callee, self.member, self.value = callee, member, value
class For(AST): 
    def __init__(self, var_name_node, start, end, step, body): self.var_name_node, self.start, self.end, self.step, self.body = var_name_node, start, end, step, body
class ForEach(AST): 
    def __init__(self, var_name_node, iterable, body): self.var_name_node, self.iterable, self.body = var_name_node, iterable, body
class ImportNode(AST): 
    def __init__(self, filename_token): self.filename_token, self.filename = filename_token, filename_token.value
class TryCatch(AST):
    def __init__(self, try_block, error_var_node, catch_block):
        self.try_block, self.error_var_node, self.catch_block = try_block, error_var_node, catch_block
class BreakNode(AST): pass
class ContinueNode(AST): pass

class Parser:
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0; self.current_token = self.tokens[self.pos]
    def error(self, message): raise ParserError(f"{message} (at {self.current_token})")
    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = Token(TokenType.EOF)

    def eat(self, token_type):
        if self.current_token.type == token_type: self.advance()
        else: self.error(f"Expected token {token_type.name}, but got {self.current_token.type.name}")

    def skip_newlines(self):
        while self.current_token.type == TokenType.NEWLINE: self.advance()

    def parse(self):
        self.skip_newlines(); statements = []
        while self.current_token.type != TokenType.EOF:
            statements.append(self.statement()); self.skip_newlines()
        return Block(statements)
    def block(self):
        self.eat(TokenType.COLON); self.eat(TokenType.NEWLINE);
        if self.current_token.type != TokenType.INDENT: self.error("Expected an indented block.")
        self.eat(TokenType.INDENT); self.skip_newlines()
        statements = []
        while self.current_token.type != TokenType.DEDENT and self.current_token.type != TokenType.EOF:
            statements.append(self.statement()); self.skip_newlines()
        if self.current_token.type == TokenType.DEDENT: self.eat(TokenType.DEDENT)
        return Block(statements)
    def statement(self):
        token_type = self.current_token.type
        if token_type == TokenType.IMPORT: return self.import_statement()
        if token_type == TokenType.MEM: return self.mem_declaration()
        if token_type == TokenType.CONST: return self.const_declaration()
        if token_type == TokenType.SHOW_SHORTHAND:
            self.eat(TokenType.SHOW_SHORTHAND)
            exprs = [self.expression()]
            while self.current_token.type == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                exprs.append(self.expression())
            return Show(exprs)
        if token_type == TokenType.SHOW: return self.show_statement()
        if token_type == TokenType.WHEN: return self.when_statement()
        if token_type == TokenType.LOOP: return self.loop_statement()
        if token_type == TokenType.FOR: return self.for_statement()
        if token_type == TokenType.TRY: return self.try_statement()
        if token_type == TokenType.BREAK: self.eat(TokenType.BREAK); return BreakNode()
        if token_type == TokenType.CONTINUE: self.eat(TokenType.CONTINUE); return ContinueNode()
        if token_type == TokenType.FN: return self.fn_definition()
        if token_type == TokenType.RETURN: self.eat(TokenType.RETURN); return Return(self.expression())
        expr = self.expression()
        if isinstance(expr, (VarAssign, MemberAssign, FnCall)): return expr
        self.error("Invalid statement. Standalone expressions are not allowed.")

    def try_statement(self):
        self.eat(TokenType.TRY)
        try_block = self.block()
        self.skip_newlines()
        self.eat(TokenType.CATCH)
        if self.current_token.type != TokenType.ID: self.error("Expected an identifier for the error variable after 'catch'")
        error_var_node = VarAccess(self.current_token)
        self.eat(TokenType.ID); catch_block = self.block(); return TryCatch(try_block, error_var_node, catch_block)

    def import_statement(self):
        self.eat(TokenType.IMPORT)
        self.skip_newlines()
        if self.current_token.type != TokenType.STRING:
            self.error("Expected a string after 'import'")
        filename_token = self.current_token
        self.eat(TokenType.STRING)
        return ImportNode(filename_token)

    def mem_declaration(self): self.eat(TokenType.MEM); name_node = VarAccess(self.current_token); self.eat(TokenType.ID); self.eat(TokenType.ASSIGN); expr = self.expression(); return VarDecl(name_node, expr)
    def const_declaration(self):
        self.eat(TokenType.CONST)
        name_node = VarAccess(self.current_token)
        self.eat(TokenType.ID); self.eat(TokenType.ASSIGN)
        expr = self.expression()
        return ConstDecl(name_node, expr)
    def show_statement(self):
        self.eat(TokenType.SHOW); expressions = []
        if self.current_token.type != TokenType.LPAREN: self.error("Expected '(' after 'show'")
        self.eat(TokenType.LPAREN)
        if self.current_token.type != TokenType.RPAREN:
            expressions.append(self.expression())
            while self.current_token.type == TokenType.COMMA: self.eat(TokenType.COMMA); expressions.append(self.expression())
        self.eat(TokenType.RPAREN); return Show(expressions)
    def when_statement(self):
        self.eat(TokenType.WHEN); condition = self.expression(); true_block = self.block()
        false_block = None; self.skip_newlines()
        if self.current_token.type == TokenType.OTHERWISE:
            self.advance()
            if self.current_token.type == TokenType.WHEN: false_block = self.when_statement()
            else: false_block = self.block()
        return When(condition, true_block, false_block)
    def loop_statement(self): self.eat(TokenType.LOOP); self.eat(TokenType.LPAREN); condition = self.expression(); self.eat(TokenType.RPAREN); body = self.block(); return Loop(condition, body)
    def for_statement(self):
        self.eat(TokenType.FOR); var_name_node = VarAccess(self.current_token); self.eat(TokenType.ID)
        if self.current_token.type == TokenType.IN:
            self.eat(TokenType.IN); iterable = self.expression(); body = self.block(); return ForEach(var_name_node, iterable, body)
        elif self.current_token.type == TokenType.FROM:
            self.eat(TokenType.FROM); start = self.expression(); self.eat(TokenType.TO); end = self.expression(); step = Number(Token(TokenType.NUMBER, 1))
            if self.current_token.type == TokenType.STEP: self.eat(TokenType.STEP); step = self.expression()
            body = self.block(); return For(var_name_node, start, end, step, body)
        else: self.error("Expected 'in' or 'from' after for loop variable.")
    def fn_definition(self):
        self.eat(TokenType.FN); name_node = VarAccess(self.current_token); self.eat(TokenType.ID); self.eat(TokenType.LPAREN); params = []
        if self.current_token.type == TokenType.ID:
            params.append(VarAccess(self.current_token)); self.eat(TokenType.ID)
            while self.current_token.type == TokenType.COMMA: self.eat(TokenType.COMMA); params.append(VarAccess(self.current_token)); self.eat(TokenType.ID)
        self.eat(TokenType.RPAREN); body = self.block(); return FnDef(name_node, params, body)
    def expression(self): return self.coalesce()
    def coalesce(self):
        node = self.assignment()
        if self.current_token.type == TokenType.NULL_COALESCE:
            op = self.current_token; self.eat(TokenType.NULL_COALESCE); node = BinOp(node, op, self.coalesce())
        return node
    def assignment(self):
        left = self.logic_or() # assignment has higher precedence than coalesce
        if self.current_token.type == TokenType.ASSIGN:
            self.eat(TokenType.ASSIGN); right = self.assignment()
            if isinstance(left, VarAccess): return VarAssign(left, right)
            if isinstance(left, MemberAccess): return MemberAssign(left.callee, left.member, right)
            self.error("Invalid assignment target.")
        return left
    def logic_or(self):
        node = self.logic_and()
        while self.current_token.type == TokenType.OR: op = self.current_token; self.eat(op.type); node = BinOp(node, op, self.logic_and())
        return node
    def logic_and(self):
        node = self.comparison()
        while self.current_token.type == TokenType.AND: op = self.current_token; self.eat(op.type); node = BinOp(node, op, self.comparison())
        return node
    def comparison(self):
        node = self.term()
        while self.current_token.type in (TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            op = self.current_token
            self.eat(op.type)
            node = BinOp(node, op, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.current_token.type in (TokenType.PLUS, TokenType.MINUS): op = self.current_token; self.eat(op.type); node = BinOp(node, op, self.factor())
        return node
    def factor(self):
        node = self.power()
        while self.current_token.type in (TokenType.MUL, TokenType.DIV, TokenType.MOD): op = self.current_token; self.eat(op.type); node = BinOp(node, op, self.power())
        return node
    def power(self):
        node = self.unary()
        if self.current_token.type == TokenType.POW: op = self.current_token; self.eat(op.type); node = BinOp(node, op, self.power())
        return node
    def unary(self):
        if self.current_token.type in (TokenType.PLUS, TokenType.MINUS): op = self.current_token; self.eat(op.type); return UnaryOp(op, self.unary())
        return self.call()
    def call(self):
        node = self.primary()
        while True:
            if self.current_token.type == TokenType.LPAREN:
                self.eat(TokenType.LPAREN); args = [];
                if self.current_token.type != TokenType.RPAREN:
                    while self.current_token.type != TokenType.RPAREN:
                        if self.current_token.type == TokenType.COMMA: self.eat(TokenType.COMMA) # Skip extra/trailing commas
                        else: args.append(self.expression())
                        if self.current_token.type == TokenType.RPAREN: break # Handle trailing comma
                self.eat(TokenType.RPAREN); node = FnCall(callee=node, args=args)
            elif self.current_token.type == TokenType.LBRACKET:
                self.eat(TokenType.LBRACKET); index_expr = self.expression(); self.eat(TokenType.RBRACKET)
                node = MemberAccess(callee=node, member=index_expr)
            elif self.current_token.type == TokenType.DOT:
                self.eat(TokenType.DOT); member_token = self.current_token; self.eat(TokenType.ID)
                member_as_string_node = String(Token(TokenType.STRING, member_token.value))
                node = MemberAccess(callee=node, member=member_as_string_node)
            else: break
        return node
    def primary(self):
        token = self.current_token
        if token.type == TokenType.LBRACE:
            self.eat(TokenType.LBRACE)
            pairs = {}
            self.skip_newlines()
            # Handle optional indentation for multi-line objects
            is_indented = self.current_token.type == TokenType.INDENT
            if is_indented: self.eat(TokenType.INDENT)
            
            if self.current_token.type != TokenType.RBRACE:
                while True:
                    self.skip_newlines()
                    key_token = self.current_token; self.eat(TokenType.STRING); self.eat(TokenType.COLON)
                    value_node = self.expression(); pairs[key_token.value] = value_node
                    self.skip_newlines()
                    if self.current_token.type == TokenType.COMMA: self.eat(TokenType.COMMA)
                    elif self.current_token.type == TokenType.RBRACE or (is_indented and self.current_token.type == TokenType.DEDENT): break
                    else: self.error("Expected comma or '}' after object value")
            
            self.skip_newlines()
            if is_indented: self.eat(TokenType.DEDENT)
            self.eat(TokenType.RBRACE)
            return ObjectLiteral(pairs)
        if token.type == TokenType.LBRACKET:
            self.eat(TokenType.LBRACKET); elements = []
            self.skip_newlines()
            if self.current_token.type != TokenType.RBRACKET:
                while self.current_token.type != TokenType.RBRACKET:
                    if self.current_token.type == TokenType.COMMA: self.eat(TokenType.COMMA) # Skip extra/trailing commas
                    else: elements.append(self.expression())
                    if self.current_token.type == TokenType.RBRACKET: break # Handle trailing comma
            self.eat(TokenType.RBRACKET); return ArrayLiteral(elements)
        if token.type == TokenType.NUMBER: self.advance(); return Number(token)
        if token.type in (TokenType.TRUE, TokenType.FALSE): self.advance(); return Boolean(token)
        if token.type == TokenType.STRING: self.advance(); return String(token)
        if token.type == TokenType.NULL: self.advance(); return NullNode(token)
        if token.type == TokenType.ID:
            self.advance()
            return VarAccess(token) # Use the original token, not the new self.current_token
        if token.type == TokenType.LPAREN:
            self.eat(TokenType.LPAREN); node = self.expression(); self.eat(TokenType.RPAREN); return node
        if token.type in (TokenType.ASK, TokenType.ASKINT, TokenType.ASKFLOAT):
            ask_type = token.type; self.eat(ask_type); self.eat(TokenType.LPAREN)
            if self.current_token.type == TokenType.RPAREN: prompt = String(Token(TokenType.STRING, ''))
            else: prompt = self.expression()
            self.eat(TokenType.RPAREN)
            num_type = 'int' if ask_type == TokenType.ASKINT else 'float' if ask_type == TokenType.ASKFLOAT else None
            return Ask(prompt, numeric_type=num_type)
        self.error(f"Unexpected token in expression: {token.type.name}")