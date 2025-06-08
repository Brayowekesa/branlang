# lexer.py

from enum import Enum

class BranError(Exception): pass
class LexerError(BranError): pass

class TokenType(Enum):
    MEM, SHOW, FN, RETURN, WHEN, OTHERWISE, LOOP, FOR, FROM, TO, STEP = 'MEM', 'SHOW', 'FN', 'RETURN', 'WHEN', 'OTHERWISE', 'LOOP', 'FOR', 'FROM', 'TO', 'STEP'
    ASK, ASKINT, ASKFLOAT, IMPORT = 'IMPORT', 'ASK', 'ASKINT', 'ASKFLOAT'
    TRUE, FALSE = 'TRUE', 'FALSE'
    IN = 'IN'
    ID, NUMBER, STRING = 'ID', 'NUMBER', 'STRING'
    PLUS, MINUS, MUL, DIV, MOD, POW = '+', '-', '*', '/', '%', '**'
    EQ, NE, LT, GT, LTE, GTE = '==', '!=', '<', '>', '<=', '>='
    AND, OR = '&&', '||'
    ASSIGN = '='
    LPAREN, RPAREN, COLON, COMMA, NEWLINE = '(', ')', ':', ',', 'NEWLINE'
    LBRACKET, RBRACKET = '[', ']'
    LBRACE, RBRACE, DOT = '{', '}', '.'
    INDENT, DEDENT, EOF = 'INDENT', 'DEDENT', 'EOF'

class Token:
    def __init__(self, type, value=None, line=0, col=0):
        self.type, self.value, self.line, self.col = type, value, line, col
    def __repr__(self):
        return f"Token({self.type.name}, {repr(self.value)})"

KEYWORDS = {
    'mem': TokenType.MEM, 'show': TokenType.SHOW, 'fn': TokenType.FN, 'return': TokenType.RETURN,
    'when': TokenType.WHEN, 'otherwise': TokenType.OTHERWISE, 'loop': TokenType.LOOP,
    'for': TokenType.FOR, 'from': TokenType.FROM, 'to': TokenType.TO, 'step': TokenType.STEP,
    'ask': TokenType.ASK, 'askInt': TokenType.ASKINT, 'askFloat': TokenType.ASKFLOAT,
    'true': TokenType.TRUE, 'false': TokenType.FALSE,
    'in': TokenType.IN, 
    'import': TokenType.IMPORT,
}

class Lexer:
    def __init__(self, text):
        self.text, self.pos, self.line, self.col = text, 0, 1, 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        self.indent_stack = [0]

    def advance(self):
        if self.current_char == '\n': self.line += 1; self.col = 1
        else: self.col += 1
        self.pos += 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None

    def peek(self):
        peek_pos = self.pos + 1
        return self.text[peek_pos] if peek_pos < len(self.text) else None

    def number(self):
        result, is_float = '', False
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == '.'):
            if self.current_char == '.':
                if is_float: break
                is_float = True
            result += self.current_char
            self.advance()
        return float(result) if is_float else int(result)

    def string(self):
        result = ''; self.advance()
        while self.current_char is not None and self.current_char != '"':
            result += self.current_char; self.advance()
        self.advance(); return result

    def identifier(self):
        result = ''
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char; self.advance()
        return result

    def get_tokens(self):
        tokens, is_start_of_line = [], True
        while self.current_char is not None:
            if is_start_of_line:
                is_start_of_line = False
                current_indent = 0
                while self.current_char == ' ':
                    current_indent += 1
                    self.advance()
                if self.current_char is not None and self.current_char not in ('\n', '/') and not self.current_char.isspace():
                    if current_indent > self.indent_stack[-1]:
                        self.indent_stack.append(current_indent)
                        tokens.append(Token(TokenType.INDENT, line=self.line, col=1))
                    while current_indent < self.indent_stack[-1]:
                        self.indent_stack.pop()
                        tokens.append(Token(TokenType.DEDENT, line=self.line, col=1))
                    if current_indent != self.indent_stack[-1]:
                        raise LexerError(f"Indentation error at line {self.line}.")
    
            if self.current_char is None:
                break
            if self.current_char.isspace() and self.current_char != '\n':
                self.advance()
                continue
    
            # --- Comment handling ---
            if self.current_char == '/':
                if self.peek() == '/':
                    # Single-line comment: Skip until end of line.
                    while self.current_char is not None and self.current_char != '\n':
                        self.advance()
                    continue
                elif self.peek() == '*':
                    # Block comment: Skip until the closing '*/'
                    self.advance()  # Consume '/'
                    self.advance()  # Consume '*'
                    while self.current_char is not None:
                        if self.current_char == '*' and self.peek() == '/':
                            self.advance()  # Consume '*'
                            self.advance()  # Consume '/'
                            break
                        else:
                            self.advance()
                    continue
    
            if self.current_char.isdigit() or (self.current_char == '.' and self.peek() and self.peek().isdigit()):
                tokens.append(Token(TokenType.NUMBER, self.number(), self.line, self.col))
            elif self.current_char.isalpha() or self.current_char == '_':
                id_str = self.identifier()
                token_type = KEYWORDS.get(id_str, TokenType.ID)
                tokens.append(Token(token_type, id_str if token_type == TokenType.ID else None, self.line, self.col))
            elif self.current_char == '"':
                tokens.append(Token(TokenType.STRING, self.string(), self.line, self.col))
            elif self.current_char == '\n':
                tokens.append(Token(TokenType.NEWLINE, '\n', self.line, self.col))
                self.advance()
                is_start_of_line = True
            elif self.current_char == '*' and self.peek() == '*':
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.POW, '**', self.line, self.col))
            elif self.current_char == '=' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.EQ, '==', self.line, self.col))
            elif self.current_char == '!' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.NE, '!=', self.line, self.col))
            elif self.current_char == '<' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.LTE, '<=', self.line, self.col))
            elif self.current_char == '>' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.GTE, '>=', self.line, self.col))
            elif self.current_char == '&' and self.peek() == '&':
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.AND, '&&', self.line, self.col))
            elif self.current_char == '|' and self.peek() == '|':
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.OR, '||', self.line, self.col))
            elif self.current_char in ('{', '}', '.', '[', ']', '+', '-', '*', '/', '%', '<', '>', '=', '(', ')', ':', ','):
                tokens.append(Token(TokenType(self.current_char), self.current_char, self.line, self.col))
                self.advance()
            else:
                raise LexerError(f"Unexpected character '{self.current_char}' at line {self.line}:{self.col}")
    
        while len(self.indent_stack) > 1:
            tokens.append(Token(TokenType.DEDENT))
            self.indent_stack.pop()
        tokens.append(Token(TokenType.EOF))
        return tokens