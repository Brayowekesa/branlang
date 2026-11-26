# lexer.py
from enum import Enum
from common import LexerError

class TokenType(Enum):
    MEM, CONST, SHOW, FN, RETURN, WHEN, OTHERWISE, LOOP, FOR, FROM, TO, STEP, IMPORT, TRY, CATCH, NULL, BREAK, CONTINUE = 'MEM','CONST','SHOW','FN','RETURN','WHEN','OTHERWISE','LOOP','FOR','FROM','TO','STEP','IMPORT','TRY','CATCH','NULL','BREAK','CONTINUE'
    ASK, ASKINT, ASKFLOAT = 'ASK', 'ASKINT', 'ASKFLOAT'
    TRUE, FALSE, IN = 'TRUE', 'FALSE', 'IN'
    ID, NUMBER, STRING = 'ID', 'NUMBER', 'STRING'
    PLUS, MINUS, MUL, DIV, MOD, POW = '+', '-', '*', '/', '%', '**'
    EQ, NE, LT, GT, LTE, GTE, SHOW_SHORTHAND = '==', '!=', '<', '>', '<=', '>=', '>'
    AND, OR, ASSIGN, NULL_COALESCE = '&&', '||', '=', '??'
    LPAREN, RPAREN, COLON, COMMA, NEWLINE = '(', ')', ':', ',', 'NEWLINE'
    LBRACKET, RBRACKET = '[', ']'
    LBRACE, RBRACE, DOT = '{', '}', '.'
    INDENT, DEDENT, EOF = 'INDENT', 'DEDENT', 'EOF'

class Token:
    def __init__(self, type, value=None, line=0, col=0): self.type, self.value, self.line, self.col = type, value, line, col
    def __repr__(self): return f"Token({self.type.name}, {repr(self.value)})"

KEYWORDS = {
    'mem': TokenType.MEM, 'const': TokenType.CONST, 'show': TokenType.SHOW, 'fn': TokenType.FN, 'return': TokenType.RETURN, 'break': TokenType.BREAK, 'continue': TokenType.CONTINUE,
    'when': TokenType.WHEN, 'otherwise': TokenType.OTHERWISE, 'loop': TokenType.LOOP,
    'for': TokenType.FOR, 'from': TokenType.FROM, 'to': TokenType.TO, 'step': TokenType.STEP, 'import': TokenType.IMPORT,
    'try': TokenType.TRY, 'catch': TokenType.CATCH, 'ask': TokenType.ASK, 'askInt': TokenType.ASKINT, 'askFloat': TokenType.ASKFLOAT, 'null': TokenType.NULL,
    'true': TokenType.TRUE, 'false': TokenType.FALSE, 'in': TokenType.IN,
}

class Lexer:
    def __init__(self, text):
        self.text, self.pos, self.line, self.col = text, 0, 1, 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        self.indent_stack = [0]

    def advance(self):
        self.pos += 1
        if self.pos > len(self.text) - 1: self.current_char = None
        else:
            self.current_char = self.text[self.pos]
            if self.current_char == '\n': self.line += 1; self.col = 0
            else: self.col += 1

    def peek(self):
        peek_pos = self.pos + 1
        if peek_pos > len(self.text) - 1: return None
        return self.text[peek_pos]

    def number(self):
        result, is_float = '', False
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == '.'):
            if self.current_char == '.':
                if is_float: break
                is_float = True
            result += self.current_char; self.advance()
        return float(result) if is_float else int(result)

    def string(self):
        result = ''; self.advance()
        while self.current_char is not None and self.current_char != '"': result += self.current_char; self.advance()
        self.advance(); return result

    def identifier(self):
        result = ''
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'): result += self.current_char; self.advance()
        return result

    def get_tokens(self):
        tokens = []
        while self.current_char is not None:
            if self.col == 1:
                if self.current_char == '\n': self.advance(); continue
                current_indent = 0
                while self.current_char == ' ': current_indent += 1; self.advance()
                # Blank and comment-only lines (# or //) are skipped entirely:
                # they don't affect indentation or emit NEWLINE tokens.
                is_comment = self.current_char == '#' or (self.current_char == '/' and self.peek() == '/')
                if is_comment or self.current_char in ('\n', '\r'):
                    while self.current_char is not None and self.current_char != '\n': self.advance()
                    if self.current_char == '\n': self.advance()
                    continue
                if self.current_char is not None:
                    if current_indent > self.indent_stack[-1]: self.indent_stack.append(current_indent); tokens.append(Token(TokenType.INDENT))
                    while current_indent < self.indent_stack[-1]: self.indent_stack.pop(); tokens.append(Token(TokenType.DEDENT))
                    if current_indent != self.indent_stack[-1]: raise LexerError(f"Indentation error at line {self.line}")
            if self.current_char is None: break
            if self.col == 1 and self.current_char == '>':
                tokens.append(Token(TokenType.SHOW_SHORTHAND, '>', self.line, self.col)); self.advance(); continue
            if self.current_char in ' \t\r': self.advance(); continue
            if self.current_char == '#':
                while self.current_char is not None and self.current_char != '\n': self.advance()
                continue
            if self.current_char == '/' and self.peek() == '/':
                while self.current_char is not None and self.current_char != '\n': self.advance()
                continue

            if self.current_char.isdigit() or (self.current_char == '.' and self.peek() and self.peek().isdigit()): tokens.append(Token(TokenType.NUMBER, self.number(), self.line, self.col))
            elif self.current_char.isalpha() or self.current_char == '_':
                id_str = self.identifier(); token_type = KEYWORDS.get(id_str, TokenType.ID); tokens.append(Token(token_type, id_str if token_type == TokenType.ID else None, self.line, self.col))
            elif self.current_char == '"': tokens.append(Token(TokenType.STRING, self.string(), self.line, self.col))
            elif self.current_char == '\n': tokens.append(Token(TokenType.NEWLINE, '\n', self.line, self.col)); self.advance()
            elif self.current_char == '*' and self.peek() == '*': self.advance(); self.advance(); tokens.append(Token(TokenType.POW, '**', self.line, self.col))
            elif self.current_char == '=' and self.peek() == '=': self.advance(); self.advance(); tokens.append(Token(TokenType.EQ, '==', self.line, self.col))
            elif self.current_char == '!' and self.peek() == '=': self.advance(); self.advance(); tokens.append(Token(TokenType.NE, '!=', self.line, self.col))
            elif self.current_char == '<' and self.peek() == '=': self.advance(); self.advance(); tokens.append(Token(TokenType.LTE, '<=', self.line, self.col))
            elif self.current_char == '>' and self.peek() == '=': self.advance(); self.advance(); tokens.append(Token(TokenType.GTE, '>=', self.line, self.col))
            elif self.current_char == '&' and self.peek() == '&': self.advance(); self.advance(); tokens.append(Token(TokenType.AND, '&&', self.line, self.col))
            elif self.current_char == '|' and self.peek() == '|': self.advance(); self.advance(); tokens.append(Token(TokenType.OR, '||', self.line, self.col))
            elif self.current_char == '?' and self.peek() == '?': self.advance(); self.advance(); tokens.append(Token(TokenType.NULL_COALESCE, '??', self.line, self.col))
            elif self.current_char in ('{', '}', '.', '[', ']', '+', '-', '*', '/', '%', '<', '>', '=', '(', ')', ':', ','):
                tokens.append(Token(TokenType(self.current_char), self.current_char, self.line, self.col)); self.advance()
            else: raise LexerError(f"Unexpected character '{self.current_char}' at line {self.line}:{self.col}")
        while len(self.indent_stack) > 1: self.indent_stack.pop(); tokens.append(Token(TokenType.DEDENT))
        tokens.append(Token(TokenType.EOF))
        return tokens