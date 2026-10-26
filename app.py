import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "atm-secret-key"      # lets Flask remember the logged-in user

DATA_FILE = "data.json"
MAX_WRONG_PINS = 3
WITHDRAW_LIMIT = 20000


def load_data():                        # read data.json -> Python dictionary
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):                    # write dictionary -> data.json
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
def add_transaction(user, kind, amount):
    user["transactions"].append({
        "time": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "type": kind,
        "amount": amount,
        "balance": user["balance"],
    })


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        acc = request.form["acc"].strip()
        pin = request.form["pin"].strip()
        data = load_data()

        if acc not in data:
            error = "Account not found."
        elif data[acc]["locked"]:
            error = "Account is locked. Contact the bank."
        elif data[acc]["pin"] == pin:
            session["acc"] = acc
            session["wrong"] = 0
            return redirect(url_for("menu"))
        else:
            session["wrong"] = session.get("wrong", 0) + 1
            left = MAX_WRONG_PINS - session["wrong"]
            if left <= 0:
                data[acc]["locked"] = True
                save_data(data)
                error = "Too many wrong attempts. Account locked."
            else:
                error = f"Wrong PIN. {left} attempt(s) left."
    return render_template("login.html", error=error)


@app.route("/menu")
def menu():
    acc = session.get("acc")
    if not acc:
        return redirect(url_for("login"))
    user = load_data()[acc]
    return render_template("menu.html", user=user, acc=acc)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
@app.route("/balance")
def balance():
    acc = session.get("acc")
    if not acc:
        return redirect(url_for("login"))
    user = load_data()[acc]
    return render_template("balance.html", user=user, acc=acc)
@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    acc = session.get("acc")
    if not acc:
        return redirect(url_for("login"))
    message, error = None, None

    if request.method == "POST":
        amount = int(request.form["amount"])
        if amount <= 0:
            error = "Enter a valid amount."
        else:
            data = load_data()
            data[acc]["balance"] += amount
            add_transaction(data[acc], "Deposit", amount)
            save_data(data)
            message = f"Rs. {amount} deposited. New balance: Rs. {data[acc]['balance']}"
    return render_template("amount.html", title="Deposit Money",
                           button="Deposit", message=message, error=error)
@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    acc = session.get("acc")
    if not acc:
        return redirect(url_for("login"))
    message, error = None, None

    if request.method == "POST":
        amount = int(request.form["amount"])
        data = load_data()
        if amount <= 0:
            error = "Enter a valid amount."
        elif amount % 100 != 0:
            error = "Amount must be a multiple of 100."
        elif amount > WITHDRAW_LIMIT:
            error = f"Limit per withdrawal is Rs. {WITHDRAW_LIMIT}."
        elif amount > data[acc]["balance"]:
            error = "Insufficient balance."
        else:
            data[acc]["balance"] -= amount
            add_transaction(data[acc], "Withdraw", amount)
            save_data(data)
            message = f"Please collect Rs. {amount}. New balance: Rs. {data[acc]['balance']}"
    return render_template("amount.html", title="Withdraw Money",
                           button="Withdraw", message=message, error=error)
@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    acc = session.get("acc")
    if not acc:
        return redirect(url_for("login"))
    message, error = None, None

    if request.method == "POST":
        to_acc = request.form["to_acc"].strip()
        amount = int(request.form["amount"])
        data = load_data()

        if to_acc not in data:
            error = "Receiver account not found."
        elif to_acc == acc:
            error = "You cannot transfer to your own account."
        elif amount <= 0:
            error = "Enter a valid amount."
        elif amount > data[acc]["balance"]:
            error = "Insufficient balance."
        else:
            data[acc]["balance"] -= amount        # money leaves sender
            data[to_acc]["balance"] += amount     # money reaches receiver
            add_transaction(data[acc], f"Sent to {to_acc}", amount)
            add_transaction(data[to_acc], f"Received from {acc}", amount)
            save_data(data)
            message = f"Rs. {amount} sent to {data[to_acc]['name']}."
    return render_template("transfer.html", message=message, error=error)
@app.route("/statement")
def statement():
    acc = session.get("acc")
    if not acc:
        return redirect(url_for("login"))
    user = load_data()[acc]
    last_five = user["transactions"][-5:][::-1]     # last 5, newest first
    return render_template("statement.html", user=user, history=last_five)
@app.route("/change_pin", methods=["GET", "POST"])
def change_pin():
    acc = session.get("acc")
    if not acc:
        return redirect(url_for("login"))
    message, error = None, None

    if request.method == "POST":
        old = request.form["old_pin"]
        new = request.form["new_pin"]
        data = load_data()

        if data[acc]["pin"] != old:
            error = "Old PIN is wrong."
        elif not (new.isdigit() and len(new) == 4):
            error = "New PIN must be exactly 4 digits."
        else:
            data[acc]["pin"] = new
            save_data(data)
            message = "PIN changed successfully."
    return render_template("change_pin.html", message=message, error=error)
@app.route("/create", methods=["GET", "POST"])
def create_account():
    message, error = None, None

    if request.method == "POST":
        name = request.form["name"].strip()
        pin = request.form["pin"].strip()
        opening = int(request.form["opening"])
        data = load_data()

        if name == "":
            error = "Name cannot be empty."
        elif not (pin.isdigit() and len(pin) == 4):
            error = "PIN must be exactly 4 digits."
        elif opening < 500:
            error = "Minimum opening balance is Rs. 500."
        else:
            new_acc = str(max(int(a) for a in data) + 1)    # next account number
            data[new_acc] = {"name": name, "pin": pin, "balance": opening,
                             "locked": False, "transactions": []}
            save_data(data)
            message = f"Account created! Your account number is {new_acc}."
    return render_template("create.html", message=message, error=error)

# ---- NEW ROUTES FROM THE NEXT STEPS GO HERE (above the lines below) ----

if __name__ == "__main__":              # keep this at the very bottom
    app.run(debug=True)
