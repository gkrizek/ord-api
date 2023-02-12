from flask import Flask, request
import subprocess
import os

app = Flask(__name__)

BITCOIND_RPC = os.environ['BITCOIND_RPC']
BITCOIND_USERNAME = os.environ['BITCOIND_USERNAME']
BITCOIND_PASSWORD = os.environ['BITCOIND_PASSWORD']


def execute_command(command, file=None, address=None, id=None, fee_rate=None, dryrun=None):
    possible_commands = [
        "send",
        "receive",
        "transactions",
        "inscribe",
        "inscriptions"
    ]
    if command not in possible_commands:
        print(f"[ERR] Received invalid command {command}.")
        return 1
    
    if command == "send":
        if address is None:
            print(f"[ERR] You must supply an address.")
            return 1
        if id is None:
            print(f"[ERR] You must supply an inscription id.")
            return 1
        if fee_rate is None:
            print(f"[ERR] You must supply a fee rate.")
            return 1
        crafted_command = f"ord wallet send {address} {id} --fee-rate={fee_rate}"
    elif command == "inscribe":
        if file is None:
            print(f"[ERR] You must supply a file path.")
            return 1
        if fee_rate is None:
            print(f"[ERR] You must supply a fee rate.")
            return 1
        if dryrun is not None:
            if type(dryrun) == bool:
                print(f"[ERR] You must supply a dry run boolean.")
                return 1
        file_path = os.path(file)
        crafted_command = f"ord wallet inscribe {file_path} --fee-rate={fee_rate} --dry-run={dryrun}"
    else:
        crafted_command = f"ord wallet {command}"

    try:
        proc = subprocess.Popen(
            crafted_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()
    except subprocess.CalledProcessError as e:
        print(f"[ERR] Failed to run command: {str(e)}")
        return 2

    if proc.returncode != 0:
        print(f"[ERR] Command returned a non zero exit code: {str(proc.returncode)}")
        print(stderr)
        print(stdout)
        return 2

    print(f"[INF] Command ran successfully with return code: {str(proc.returncode)}")
    print(stderr)
    print(stdout)
    return 0


def download_file():
    return


def delete_file():
    return


def get_fee_rates():
    return


# API Endpoints
@app.post("/api/send")
def send():
    print(request.get_json())
    return "ok"


@app.post("/api/inscribe")
def inscribe():
    print(request.get_json())
    return "ok"


@app.get("/api/receive")
def receive():
    print(request.get_json())
    return "ok"


@app.get("/api/transactions")
def transactions():
    print(request.get_json())
    return "ok"


@app.get("/api/inscriptions")
def inscriptions():
    print(request.get_json())
    return "ok"