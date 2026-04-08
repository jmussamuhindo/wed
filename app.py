from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    # ✅ Wedding day starts at midnight (so days change at midnight)
    wedding_date = datetime(2026, 6, 20, 0, 0, 0)

    # ✅ Today's date at midnight
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ✅ Difference in full days
    days_left = (wedding_date - today).days

    return render_template("index.html", days_left=days_left)

if __name__ == "__main__":
    app.run(debug=True)