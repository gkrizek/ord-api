from flask import Flask, request, Response
import subprocess
import requests
import os
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)
s3 = boto3.client("s3")

BITCOIN_NETWORK = os.environ['BITCOIN_NETWORK']
BITCOIND_RPC = os.environ['BITCOIND_RPC']
S3_BUCKET = os.environ['S3_BUCKET']


def execute_command(command, file=None, address=None, id=None, fee_rate=None, dryrun=None):
    possible_commands = [
        "send",
        "receive",
        "transactions",
        "inscribe",
        "inscriptions",
        "fee_rate"
    ]
    if command not in possible_commands:
        print(f"[ERR] Received invalid command {command}.")
        return "", 1
    
    if command == "fee_rate":
        crafted_command = [
            "bitcoin-cli",
            "-conf=/etc/bitcoin/bitcoin.conf",
            "estimatesmartfee",
            fee_rate,
            "unset"
        ]
    elif command == "send":
        if address is None:
            print(f"[ERR] You must supply an address.")
            return "", 1
        if id is None:
            print(f"[ERR] You must supply an inscription id.")
            return "", 1
        if fee_rate is None:
            print(f"[ERR] You must supply a fee rate.")
            return "", 1
        crafted_command = [
            "ord",
            f"--chain={BITCOIN_NETWORK}",
            "--rpc-url=127.0.0.1",
            "--cookie-file=/bitcoin/wallet.cookie",
            "--data-dir=/ord",
            "wallet", "send",
            address, id,
            f"--fee-rate={fee_rate}"
        ]
    elif command == "inscribe":
        if file is None:
            print(f"[ERR] You must supply a file path.")
            return "", 1
        if fee_rate is None:
            print(f"[ERR] You must supply a fee rate.")
            return "", 1
        if dryrun is not None:
            if type(dryrun) == bool:
                print(f"[ERR] You must supply a dry run boolean.")
                return "", 1
        file_path = os.path(file)
        crafted_command = [
            "ord",
            f"--chain={BITCOIN_NETWORK}",
            "--rpc-url=127.0.0.1",
            "--cookie-file=/bitcoin/wallet.cookie",
            "--data-dir=/ord",
            "wallet", "inscribe",
            file_path,
            f"--fee-rate={fee_rate}",
            f"--dry-run={dryrun}"
        ]
    else:
        crafted_command = [
            "ord",
            f"--chain={BITCOIN_NETWORK}",
            "--rpc-url=127.0.0.1",
            "--cookie-file=/bitcoin/wallet.cookie",
            "--data-dir=/ord",
            "wallet", command
        ]

    try:
        proc = subprocess.Popen(
            crafted_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()
    except subprocess.CalledProcessError as e:
        print(f"[ERR] Failed to run command: {str(e)}")
        return "", 2

    if proc.returncode != 0:
        print(f"[ERR] Command returned a non zero exit code: {str(proc.returncode)}")
        print(str(stderr))
        print(str(stdout))
        return "", 2

    print(f"[INF] Command ran successfully with return code: {str(proc.returncode)}")
    print(str(stderr))
    print(str(stdout))
    return stdout, 0


def download_file(path):
    try:
        with open(f"/ord/api/{path}", "wb") as data:
            s3.download_fileobj(S3_BUCKET, path, data)
        print("[INF] File downloaded successfully")
    except ClientError as e:
        print("[ERR] Failed to download file: {e}")
        return 1
    return 0


def delete_file(path):
    os.remove(f"/ord/api/{path}")
    return


def get_fee_rates(file_size):
    current_rate_fast, fast_status = execute_command("fee_rate", file=None, address=None, id=None, fee_rate=1, dryrun=None)
    if fast_status != 0:
        return "", 2
    current_rate_medium, medium_status = execute_command("fee_rate", file=None, address=None, id=None, fee_rate=10, dryrun=None)
    if medium_status != 0:
        return "", 2
    current_rate_slow, slow_status = execute_command("fee_rate", file=None, address=None, id=None, fee_rate=25, dryrun=None)
    if slow_status != 0:
        return "", 2

    file_size_in_kb = file_size / 1000
    fast_fee = file_size_in_kb * current_rate_fast
    medium_fee = file_size_in_kb * current_rate_medium
    slow_fee = file_size_in_kb * current_rate_slow

    response = {
        "slow": {
            "target_blocks": 25,
            "total_fee": slow_fee    
        },
        "medium": {
            "target_blocks": 10,
            "total_fee": medium_fee    
        },
        "fast": {
            "target_blocks": 1,
            "total_fee": fast_fee    
        }
    }
    return response, 0


# API Endpoints
@app.post("/api/send")
def send():
    print("[INF] Processing /api/send")
    input = request.get_json()
    if input is None:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    print(f"[INF] Found data in request {input}")

    try:
        address = input['address']
        id = input['inscription_id']
    except KeyError:
        return Response('{"status":"missing required fields"}', status=400, mimetype='application/json')
    
    if "fee_rate" in input:
        fee_rate = input['fee_rate']
    else:
        fee_rate = get_fee_rates(0)['slow']['rate']

    output, status = execute_command("send", file=None, address=address, id=id, fee_rate=fee_rate, dryrun=None)
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(output, status=200, mimetype='application/json')


@app.post("/api/inscribe")
def inscribe():
    print("[INF] Processing /api/inscribe")
    input = request.get_json()
    if input is None:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    print(f"[INF] Found data in request {input}")

    try:
        file_path = input['file_path']
    except KeyError:
        return Response('{"status":"missing required fields"}', status=400, mimetype='application/json')
    
    if "fee_rate" in input:
        fee_rate = input['fee_rate']
    else:
        fee_rate = get_fee_rates(0)['slow']['rate']
    if "dryrun" in input:
        dryrun = input['dryrun']
    else:
        dryrun = None

    status = download_file(file_path)
    if status != 0:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')

    output, status = execute_command("send", file=file_path, address=None, id=None, fee_rate=fee_rate, dryrun=dryrun)
    delete_file(file_path)
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(output, status=200, mimetype='application/json')


@app.get("/api/receive")
def receive():
    print("[INF] Processing /api/receive")
    output, status = execute_command("receive")
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(output, status=200, mimetype='application/json')


@app.get("/api/transactions")
def transactions():
    print("[INF] Processing /api/transactions")
    output, status = execute_command("transactions")
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(output, status=200, mimetype='application/json')


@app.get("/api/inscriptions")
def inscriptions():
    print("[INF] Processing /api/inscriptions")
    output, status = execute_command("inscriptions")
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(output, status=200, mimetype='application/json')


@app.post("/api/estimate_fees")
def estimate_fees():
    print("[INF] Processing /api/estimate_fees")
    input = request.get_json()
    if input is None:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    print(f"[INF] Found data in request {input}") 

    try:
        file_size_bytes = input['file_size_bytes']
    except KeyError:
        return Response('{"status":"missing required fields"}', status=400, mimetype='application/json')

    output, status = get_fee_rates(file_size_bytes)
    if status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(output, status=200, mimetype='application/json')