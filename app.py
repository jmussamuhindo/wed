from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    # Set wedding date at midnight to avoid time‑of‑day issues
    wedding_date = datetime(2026, 6, 20, 0, 0, 0)

    # Current date normalized to midnight
    today = datetime.now().replace(hour=00, minute=00, second=00, microsecond=00)

    days_left = (wedding_date - today).days

    return render_template("index.html", days_left=days_left)

if __name__ == "__main__":
    # Use debug only locally, not on Render
    app.run(debug=True)