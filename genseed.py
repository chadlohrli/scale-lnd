import base64, codecs, json, requests
import os
url = 'https://localhost:8001/v1/genseed'
cert_path = os.path.expanduser('~/.lnd/tls.cert')
r = requests.get(url,verify=cert_path)
print(r.json()['cipher_seed_mnemonic'])

