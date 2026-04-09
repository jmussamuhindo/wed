from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    # Days banner and countdown are fully driven by JavaScript
    # so the page stays accurate without needing a page refresh.
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)