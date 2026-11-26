from flask import Flask, render_template, request, jsonify
import io, contextlib, os
import requests
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Use centralized runner from branlang.py
from branlang import run

app = Flask(__name__, template_folder='templates')


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
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return jsonify({"error": "Missing Google API Key"}), 500

    data = request.get_json() or {}
    user_code = data.get('code', '')

    # Prepare the prompt for BranLang
    prompt_text = f"""
    You are an expert coder in a language called BranLang.
    BranLang syntax uses 'mem' for variables, 'fn' for functions, 'show' for output.
    Complete the following code snippet. Do not explain, just provide the code completion.
    
    Code:
    {user_code}
    """

    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }

    try:
        response = requests.post(gemini_url, json=payload, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            result = response.json()
            # Extract text from Gemini response structure
            completion = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '// AI returned no text')
            return jsonify({"completion": completion})
        else:
            return jsonify({"error": f"AI Error: {response.status_code} - {response.text}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)