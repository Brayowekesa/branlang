from flask import Flask, render_template, request, jsonify
import sys
import os
from io import StringIO
from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError

# Load environment variables from .env file
load_dotenv()

# Import all your BranLang components
from lexer import Lexer
from parser_ast import Parser
from interpreter import Interpreter
from common import BranError, LexerError, ParserError, InterpreterError

app = Flask(__name__)

# --- SECURELY INITIALIZE OPENAI CLIENT ---
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file.")
    client = OpenAI(api_key=api_key)
    print("✅ OpenAI client initialized successfully.")
except Exception as e:
    print(f"🔴 WARNING: Could not initialize OpenAI client. AI features will be disabled. Error: {e}")
    client = None

def run_branlang_code(source_code, stdin_text):
    """Executes BranLang code and captures its output or error."""
    old_stdout = sys.stdout
    redirected_output = StringIO()
    sys.stdout = redirected_output
    try:
        lexer = Lexer(source_code)
        tokens = lexer.get_tokens()
        parser = Parser(tokens)
        ast = parser.parse()
        # Pass the stdin_text to the Interpreter
        interpreter = Interpreter(stdin_text=stdin_text)
        interpreter.interpret(ast)
        output = redirected_output.getvalue()
        return {"output": output, "error": None}
    except BranError as e:
        return {"output": None, "error": f"BranLang Error: {e}"}
    finally:
        sys.stdout = old_stdout

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run():
    data = request.get_json()
    code = data.get('code', '')
    stdin = data.get('stdin', '')
    result = run_branlang_code(code, stdin)
    return jsonify(result)

@app.route('/complete', methods=['POST'])
def complete():
    """Handles AI code completion with robust error handling."""
    if not client:
        return jsonify({"error": "AI client is not configured on the server."}), 500

    data = request.get_json()
    code_prompt = data.get('code', '')
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a BranLang programming assistant. Provide only code completions without explanation or markdown."},
                {"role": "user", "content": f"Complete the following BranLang code:\n\n```branlang\n{code_prompt}```"}
            ],
            temperature=0.2, max_tokens=60, timeout=15.0
        )
        completed_code = completion.choices[0].message.content.strip()
        return jsonify({"completion": completed_code})
    except AuthenticationError:
        error_msg = "AI Error: Authentication failed. Check your OpenAI API key and billing status."
        print(f"🔴 {error_msg}")
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_msg = f"AI service error: {e}"
        print(f"🔴 {error_msg}")
        return jsonify({"error": error_msg}), 500

if __name__ == '__main__':
    app.run(debug=True)