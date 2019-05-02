from flask import Flask, request, jsonify
import os
import requests
import string
import random
import base64, codecs, json
import time

url = 'https://localhost:8001/v1'
cert_path = os.path.expanduser('~/.lnd/tls.cert')
macaroon_path = os.getcwd() + '/data/chain/bitcoin/simnet/admin.macaroon'

app = Flask(__name__)
@app.route('/getinfo', methods=['GET','POST'])
def getinfo():
	if request.method == 'POST':
		input_json = request.get_json()
		print(input_json)
		getinfo_url = url + '/getinfo'	
		r = requests.get(getinfo_url, verify=cert_path)
		print(r.json())
		return jsonify(r.json())


@app.route('/test')
def test():
	return "hello world"

@app.route('/create', methods=['GET','POST'])
def create():
	ret_dict = {}

	lnd_cmd = "lnd --rpclisten=localhost:10001 --listen=localhost:10011 --restlisten=localhost:8001 --bitcoin.simnet --bitcoin.node=btcd\n"
	screen_lnd_cmd = "screen -S lndt -X stuff " + "\"" + lnd_cmd + "\""
	create_screen_cmd = "screen -dmS lndt"
	os.system(create_screen_cmd)
	os.system(screen_lnd_cmd)
	
	time.sleep(1)

	pw, seed = initWallet()

	time.sleep(5)

	address = initAddress()	

	ret_dict['password'] = pw
	ret_dict['seed'] = seed
	ret_dict['address'] = address

	print(ret_dict)

	return jsonify(ret_dict)

def initWallet():
	
	#create wallet
	url = 'https://localhost:8001/v1/initwallet'
	pw = generate_pw()
	seed = generate_seed()

	data = {
		'wallet_password': base64.b64encode(pw).decode(),
		'cipher_seed_mnemonic': seed	
	}

	r = requests.post(url, verify=cert_path, data=json.dumps(data))
	
	return pw,seed

def initAddress():
	address_url = 'https://localhost:8001/v1/newaddress'
	macaroon = codecs.encode(open(macaroon_path,'rb').read(), 'hex')
	headers = {'Grpc-Metadata-macaroon': macaroon}
	r = requests.get(address_url, headers=headers, verify=cert_path)
	
	return r.json()['address']

def generate_pw():
	chars = string.letters + string.digits + string.punctuation
	pw = ""
	for i in range(8):
		pw += random.choice(chars)
	
	print(pw)
	return pw

def generate_seed():
	seed_url = 'https://localhost:8001/v1/genseed'
  	r = requests.get(seed_url,verify=cert_path)
  	return r.json()['cipher_seed_mnemonic']


if __name__ == '__main__':
	app.run(port='5002')
