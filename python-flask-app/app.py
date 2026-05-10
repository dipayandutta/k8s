import os

from flask import Flask

app = Flask(__name__)

CURRENT_FILE = "/data/visits.txt"


def read_counter():
    if not os.path.exists(CURRENT_FILE):
        with open(CURRENT_FILE, "w") as f:
            f.write("0")

    with open(CURRENT_FILE, "r") as f:
        count = int(f.read())

    return count


def write_counter(count):
    with open(CURRENT_FILE, "w") as f:
        f.write(str(count))


@app.route("/")
def home():
    count = read_counter()
    count += 1
    write_counter(count)

    return f"""
    <h1>Hello Flask from k8s</h1>
    <h2>Visit Count: {count}</h2>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
