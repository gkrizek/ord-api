# ord-api
API for managing Ord

## Running the API

```
$ pip3 install flask boto3
$ BITCOIN_RPC=localhost:8443 \
    BITCOIN_USERNAME=admin \
    BITCOIN_PASSWORD=supersecret \
    S3_BUCKET=mybucket \
    FLASK_APP=api \
    flask run
```

## Endpoints:

- `GET /api/receive`

Response:

```
{}
```

- `GET /api/transactions`

Response:

```
{}
```

- `GET /api/inscriptions`

Response:

```
{}
```

- `POST /api/fee`

Request:

```
{
    "file_size_bytes": 34235435
}
```

Response:

```
{
    "slow": {
        "rate": 2,
        "total": 2342    
    },
    "medium": {
        "rate": 6,
        "total": 8356    
    },
    "fast": {
        "rate": 12,
        "total": 15323    
    },
}
```

- `POST /api/inscribe`

Request:

```
{
    "file_path": "",
    "fee_rate": "",
    "dryrun": false
}
```

Response:

```
{}
```

- `POST /api/send`

Request:

```
{
    "address": "tb1ql2rd4tsvv8ykka24vywzpz6w7menvzy0dak6w4",
    "inscription_id": "abc123",
    "fee_rate": ""
}
```

Response:

```
{}
```