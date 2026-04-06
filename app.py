from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    wedding_date = datetime(2026, 6, 20)
    today = datetime.now()
    days_left = (wedding_date - today).days

    return render_template("index.html", days_left=days_left)

if __name__ == "__main__":
    app.run(debug=True)