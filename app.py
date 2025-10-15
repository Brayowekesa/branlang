from flask import Flask, render_template, request, jsonify
import io, contextlib, os
from dotenv import load_dotenv

# Optional OpenAI client import (fail gracefully if not installed/configured)
try:
    from openai import OpenAI, AuthenticationError
except Exception:
    OpenAI = None
    AuthenticationError = Exception

# Load .env
load_dotenv()

# Use centralized runner from branlang.py
from branlang import run

app = Flask(__name__, template_folder='templates')

# Initialize OpenAI client if API key present
client = None
if OpenAI is not None:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            client = OpenAI(api_key=api_key)
        except Exception as e:
            print(f"Warning: OpenAI client init failed: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_code():
    data = request.get_json() or {}
    source = data.get('code', '')
    stdin_text = data.get('stdin', None)  # None => interactive mode, "" => batch zero-lines

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            # pass stdin_text exactly as provided; branlang.run interprets None vs ""
            run(source, stdin_text=stdin_text)
        return jsonify({"ok": True, "output": buf.getvalue()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "output": buf.getvalue()}), 400

@app.route('/complete', methods=['POST'])
def complete():
    if client is None:
        return jsonify({"error": "AI client not configured."}), 500

    data = request.get_json() or {}
    code_prompt = data.get('code', '')
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a BranLang programming assistant. Provide only code completions without explanation or markdown."},
                {"role": "user", "content": f"Complete the following BranLang code:\n\n```branlang\n{code_prompt}```"}
            ],
            temperature=0.2, max_tokens=200, timeout=15.0
        )
        completed_code = completion.choices[0].message.content.strip()
        return jsonify({"completion": completed_code})
    except AuthenticationError:
        return jsonify({"error": "AI authentication failed."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)