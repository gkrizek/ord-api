from flask import Flask, request, Response, jsonify
import subprocess
import requests
import os
import json
import base64
import boto3
from botocore.exceptions import ClientError

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
s3 = boto3.client("s3")

BITCOIN_NETWORK = os.environ['BITCOIN_NETWORK']
BITCOIND_RPC = os.environ['BITCOIND_RPC']
S3_BUCKET = os.environ['S3_BUCKET']
ORD_URL = os.environ['ORD_URL']


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
            str(fee_rate),
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
            f"--fee-rate={str(fee_rate)}"
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
            f"--fee-rate={str(fee_rate)}",
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
    print(f"[INF] Calculating fee rates...")
    request_fast, fast_status = execute_command("fee_rate", file=None, address=None, id=None, fee_rate=1, dryrun=None)
    if fast_status != 0:
        return "", 2
    current_rate_fast = '%f' % json.loads(request_fast)["feerate"]
    request_medium, medium_status = execute_command("fee_rate", file=None, address=None, id=None, fee_rate=10, dryrun=None)
    if medium_status != 0:
        return "", 2
    current_rate_medium = '%f' % json.loads(request_medium)["feerate"]
    request_slow, slow_status = execute_command("fee_rate", file=None, address=None, id=None, fee_rate=25, dryrun=None)
    if slow_status != 0:
        return "", 2
    current_rate_slow = '%f' % json.loads(request_slow)["feerate"]

    file_size_in_kb = round(file_size / 1000)
    fast_fee = file_size_in_kb * float(current_rate_fast)
    medium_fee = file_size_in_kb * float(current_rate_medium)
    slow_fee = file_size_in_kb * float(current_rate_slow)
    print(f"[INF] File Size in Kilobytes: {str(file_size_in_kb)}")
    print(f"[INF] Fee Rate for Fast: {str(current_rate_fast)}")
    print(f"[INF] Fee Rate for Medium:  {str(current_rate_medium)}")
    print(f"[INF] Fee Rate for Small: {str(current_rate_slow)}")


    response = {
        "slow": {
            "target_blocks": 25,
            "total_fee": '{:.8f}'.format(slow_fee)
        },
        "medium": {
            "target_blocks": 10,
            "total_fee": '{:.8f}'.format(medium_fee)
        },
        "fast": {
            "target_blocks": 1,
            "total_fee":'{:.8f}'.format(fast_fee)
        }
    }
    return response, 0


def get_json_from_request(request):
    result = request.split('<main>')[1].split('</main>')[0]
    final = result.replace(" ", "").replace('\\n', '').replace('",]', '"]')
    return json.loads(final)


'''
API Endpoints
'''
# Home
@app.get("/")
def get_docs():
    f = open('index.html', 'r').read()
    return Response(f, status=200)


# WIP Routes
@app.post("/wip/api/send")
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
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.post("/wip/api/inscribe")
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
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.get("/wip/api/receive")
def receive():
    print("[INF] Processing /api/receive")
    output, status = execute_command("receive")
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.get("/wip/api/transactions")
def transactions():
    print("[INF] Processing /api/transactions")
    output, status = execute_command("transactions")
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.get("/wip/api/inscriptions")
def inscriptions():
    print("[INF] Processing /api/inscriptions")
    output, status = execute_command("inscriptions")
    if status == 1:
        return Response('{"status":"bad request"}', status=400, mimetype='application/json')
    elif status == 2:
        return Response('{"status":"internal server error"}', status=500, mimetype='application/json')
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.post("/wip/api/estimate_fees")
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
    return Response(json.dumps(output), status=200, mimetype='application/json')

# Functional Routes
@app.get("/api/inscription/<id>")
def get_inscription(id):
    req = requests.get(f"http://{ORD_URL}/inscription/{id}")
    if req.status_code != 200:
        print(f"[ERR] Got bad status code from Ord: {req.status_code}")
        content = str(req.content)
        print(f"[ERR] Ord response:: {content}") 
        return Response('{"status":"' + str(content) + '"}', status=req.status_code, mimetype='application/json')
    content = str(req.content)
    output = get_json_from_request(content)
    del output['content']
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.get("/api/inscription/<id>/content")
def get_inscription_content(id):
    # Get Content
    req = requests.get(f"http://{ORD_URL}/content/{id}")
    if req.status_code != 200:
        print(f"[ERR] Got bad status code from Ord: {req.status_code}")
        content = str(req.content)
        print(f"[ERR] Ord response:: {content}") 
        return Response('{"status":"' + str(content) + '"}', status=req.status_code, mimetype='application/json')
    content = req.content
    data = base64.b64encode(content).decode('utf-8')
    # Get Content Type
    req = requests.get(f"http://{ORD_URL}/inscription/{id}")
    if req.status_code != 200:
        print(f"[ERR] Got bad status code from Ord: {req.status_code}")
        content = str(req.content)
        print(f"[ERR] Ord response:: {content}") 
        return Response('{"status":"' + str(content) + '"}', status=req.status_code, mimetype='application/json')
    content = str(req.content)
    type_output = get_json_from_request(content)
    content_type = type_output['content_type']
    output = {
        "content": data,
        "content_type": content_type
    }
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.get("/api/utxo/<id>")
def get_utxo(id):
    req = requests.get(f"http://{ORD_URL}/output/{id}")
    if req.status_code != 200:
        print(f"[ERR] Got bad status code from Ord: {req.status_code}")
        content = str(req.content)
        print(f"[ERR] Ord response:: {content}") 
        return Response('{"status":"' + str(content) + '"}', status=req.status_code, mimetype='application/json')
    content = str(req.content)
    output = get_json_from_request(content)
    return Response(json.dumps(output), status=200, mimetype='application/json')


@app.get("/api/address/<id>")
def get_address(id):
    # Get all UTXOs for Address
    if BITCOIN_NETWORK == "testnet":
        esplora_url = f"https://mempool.space/testnet/api/address/{id}/txs"
    elif BITCOIN_NETWORK == "signet":
        esplora_url = f"https://mempool.space/signet/api/address/{id}/txs"
    else: 
        esplora_url = f"https://mempool.space/api/address/{id}/txs"
    req = requests.get(esplora_url)
    if req.status_code != 200:
        print(f"[ERR] Got bad status code from Ord: {req.status_code}")
        content = str(req.content)
        print(f"[ERR] Ord response:: {content}") 
        return Response('{"status":"' + str(content) + '"}', status=req.status_code, mimetype='application/json')
    tx_list = req.json()
    utxo_list = []
    inscription_list = []
    for tx in tx_list:
        print(tx)
        for index, out in enumerate(tx['vout']):
            if out['scriptpubkey_address'] == id:
                utxo_list.append(f"{tx['txid']}:{index}")

    for utxo in utxo_list:
        print(utxo)
        req = requests.get(f"http://{ORD_URL}/output/{utxo}")
        if req.status_code == 404:
            continue
        if req.status_code != 200:
            print(f"[ERR] Got bad status code from Ord: {req.status_code}")
            content = str(req.content)
            print(f"[ERR] Ord response:: {content}") 
            return Response('{"status":"' + str(content) + '"}', status=req.status_code, mimetype='application/json')
        content = str(req.content)
        utxo_output = get_json_from_request(content)
        if len(utxo_output['inscriptions']) > 0:
            inscription_list.append({
                "inscriptions": utxo_output['inscriptions'],
                "output": utxo
            })
    output = {
        "address": id,
        "inscriptions": inscription_list
    }
    return Response(json.dumps(output), status=200, mimetype='application/json')


if __name__ == '__main__':
    context = ('default.crt', 'default.key')
    app.run(ssl_context=context)