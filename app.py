from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    # FIX: Wedding ceremony starts at 14:00, not midnight
    wedding_date = datetime(2026, 6, 20, 14, 0, 0)

    # Today's date at midnight for a clean full-days count
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # FIX: max(..., 0) prevents negative days after the wedding
    days_left = max((wedding_date - today).days, 0)

    return render_template("index.html", days_left=days_left)


if __name__ == "__main__":
    app.run(debug=True)