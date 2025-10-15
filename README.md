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
    *   AI-powered code completion (press `Tab` to complete your code).
    *   Light and Dark mode support.

## 🕹️ The BranLang™ Playground (Web IDE)

The easiest way to get started with BranLang is through its web-based IDE.

### Prerequisites

*   Python 3.x
*   An OpenAI API Key (for the AI features)

### Running the IDE

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/branlang.git
    cd branlang
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(You will need to create a `requirements.txt` file. See below.)*

3.  **Set Up Your API Key:**
    *   Create a file named `.env` in the root of the project directory.
    *   Add your OpenAI secret key to this file:
      ```
      OPENAI_API_KEY="sk-YourSecretKeyGoesHere"
      ```

4.  **Run the Web Server:**
    ```bash
    python app.py
    ```

5.  **Open Your Browser:** Navigate to **`http://127.0.0.1:5000`**. You should now see the BranLang IDE, ready for you to code!

### Creating `requirements.txt`
