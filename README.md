# BranLang™ 🚀

 <!-- Optional: Add a screenshot of your IDE here -->

Welcome to the official repository for **BranLang™**, a dynamic, interpreted programming language built from the ground up in Python. BranLang is designed to be simple, readable, and powerful, incorporating modern features like arrays and objects with an intuitive, unique syntax.

This project includes not only the language interpreter but also a full-featured, AI-powered web IDE for writing and running BranLang code directly in your browser.

## ✨ Features

BranLang is a fully-featured scripting language that supports:

*   **Clean Syntax:** Indentation-based blocks and intuitive keywords make for readable and elegant code.
*   **Rich Data Types:**
    *   Numbers (Integers and Floats)
    *   Strings
    *   Booleans (`true`, `false`)
*   **Powerful Data Structures:**
    *   **Arrays (Lists):** `mem my_list = [1, "two", 3.0]`
    *   **Objects (Dictionaries):** `mem user = {"name": "Alex", "score": 100}`
*   **Modern Control Flow:**
    *   `when/otherwise when/otherwise` for clean conditional logic.
    *   `loop (condition)` for `while`-style loops.
    *   `for i from 1 to 10` for classic counting loops.
    *   `for item in my_list` for easy iteration over arrays.
*   **First-Class Functions:** Define functions with `fn`, accept parameters, and `return` values.
*   **Built-in Standard Library:** Includes functions for math (`sqrt`, `round`), array manipulation (`len`, `push`, `pop`), and I/O (`show`, `askInt`).
*   **AI-Augmented Web IDE:**
    *   A beautiful web-based editor with syntax highlighting.
    *   AI-powered code completion (press `Tab` to complete your code) using Google Gemini.
    *   Light and Dark mode support.

## 🕹️ The BranLang™ Playground (Web IDE)

The easiest way to get started with BranLang is through its web-based IDE.

### Prerequisites

*   Python 3.x
*   A Google AI API Key (for the AI features)

### Running the IDE

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Brayowekesa/branlang.git
    cd branlang
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set Up Your API Key:**
    *   Create a file named `.env` in the root of the project directory.
    *   Add your Google AI API key to this file:
      ```
      GOOGLE_API_KEY="YourGoogleApiKeyGoesHere"

      # Optional: Specify a different Gemini model (defaults to gemini-pro)
      # GEMINI_MODEL="gemini-1.5-pro-latest"
      ```

4.  **Run the Web Server:**
    ```bash
    python app.py
    ```

5.  **Open Your Browser:** Navigate to **`http://127.0.0.1:5000`**. You should now see the BranLang IDE, ready for you to code!

### Creating `requirements.txt`
```text
Flask==3.0.0
python-dotenv==1.0.0
google-generativeai>=0.8.3
```

## Running BranLang Files

```bash
python branlang.py my_program.bl          # compile to bytecode and run on the VM (default)
python branlang.py --ast my_program.bl    # tree-walking AST interpreter
python branlang.py --dis my_program.bl    # print the compiled bytecode instead of running
```

Set `BRANLANG_ENGINE=ast` to make the AST interpreter the default (this also applies to the web IDE).

The bytecode engine lives in `bytecode.py` (opcodes and chunks), `compiler.py` (AST → bytecode)
and `vm.py` (stack-based VM). It supports everything the AST interpreter does, including
closures (nested functions that capture and update variables of the scope they were defined in),
and produces identical output on the whole test suite.

## Running the Tests

Each `tests/<name>.bl` is run and its output compared with `tests/<name>.out`
(`<name>.in` supplies input, `<name>.err` marks an expected error):

```bash
python run_tests.py        # bytecode VM
python run_tests.py --ast  # AST interpreter (skips tests marked `// vm-only` on their first line)
```
