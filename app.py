from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    # Set wedding date at midnight to avoid time‑of‑day issues
    wedding_date = datetime(2026, 6, 20, 23, 59, 59)

    # Current date normalized to midnight
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    days_left = (wedding_date - today).days

    return render_template("index.html", days_left=days_left)

if __name__ == "__main__":
    # Use debug only locally, not on Render
    app.run(debug=True)
    