from flask import Flask, request, jsonify
import os
import requests
import string
import random
import base64, codecs, json
import time

base_url = 'https://localhost:8001/v1/'
cert_path = os.path.expanduser('~/.lnd/tls.cert')
macaroon_path = os.path.expanduser('~/.lnd/data/chain/bitcoin/simnet/admin.macaroon')
macaroon = codecs.encode(open(macaroon_path,'rb').read(), 'hex')
headers = {'Grpc-Metadata-macaroon': macaroon}	

app = Flask(__name__)

@app.route('/test')
def test():
	return "hello world"

@app.route('/getinfo', methods=['GET','POST'])
def getinfo():

	getinfo_url = base_url + 'getinfo'

	try:
		r = requests.get(getinfo_url, headers=headers, verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node getinfo'})

	return jsonify(r.json())

@app.route('/walletbalance', methods=['GET'])
def walletbalance():

	wbalance_url = base_url + 'balance/blockchain'
	
	try:
		r = requests.get(wbalance_url, headers=headers, verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node walletbalance'})
	
	return jsonify(r.json())

@app.route('/channelbalance', methods=['GET'])
def channelbalance():

	cbalance_url = base_url + 'balance/channels'
	
	try:
		r = requests.get(cbalance_url, headers=headers, verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node channelbalance'})

	return jsonify(r.json())	

@app.route('/peers', methods=['GET'])
def peers():

	peers_url = base_url + 'peers'

	try:
		r = requests.get(cbalance_url, headers=headers, verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node peers'})

	return jsonify(r.json())
	
# example: http://127.0.0.1/connect?pubkey=abc&host=127.0.0.1:8001
@app.route('/connect', methods=['GET'])
def connect():

	pubkey = request.args.get('pubkey')
	host = request.args.get('host')
	
	if(not pubkey or not host):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'lnd node connect'})

	connect_url = base_url + 'peers'

	data = {
		'addr': {
			'pubkey': pubkey,
			'host': host
		},
		'perm': False
	}

	try:
		r = requests.post(connect_url, headers=headers, verify=cert_path, data=json.dumps(data))
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node connect'})

	return jsonify(r.json())

#example: https://127.0.0.1/channel?pubkey=abc&amt=800000&pushamt=200000
@app.route('/openchannel', methods=['GET'])
def openchannel():

	pubkey = request.args.get('pubkey')
	amt	= request.args.get('amt')
	pushamt = request.args.get('pushamt')

	if(not pubkey or not amt):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'lnd node openchannel'})

	channel_url = base_url + 'channels'

	if(pushamt):
		data = {
			'node_pubkey_string': pubkey,
			'local_funding_amount': amt,
			'push_sat': pushamt
		}
	else:
		data = {
			'node_pubkey_string': pubkey,
			'local_funding_amount': amt
		}

	#sync wallet before opening channel
	generateBlocks(1)

	try:
		r = requests.post(channel_url, headers=headers, verify=cert_path, data=json.dumps(data))
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node openchannel'})	
	
	#mine channel transaction (6 blocks)
	generateBlocks(6)

	return jsonify(r.json())

#example: https://127.0.0.1/closechannel?pubkey=abc
@app.route('/closechannel', methods=['GET'])
def closechannel():
	
	pubkey = request.args.get('pubkey')
	
	if(not pubkey):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'lnd node closechannel'})

	channel_url = base_url + 'channels'
	channel = getchannel(pubkey)

	if(len(channel) != 0):
		cp = channel['channel_point'].split(':')
		d_channel_url = channel_url + '/' + cp[0] + '/' + cp[1]

		try:
			r = requests.delete(d_channel_url, headers=headers, verify=cert_path, stream=True)
			r.raise_for_status()
		except requests.exceptions.RequestException as err:
			return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node closechannel'})	

		#note we need to mine 1 block toclose channel tx
		for raw_response in r.iter_lines():
			json_response = json.loads(raw_response)
			print(json_response)
			generateBlocks(1)

		return jsonify(json_response)
	else:
		return jsonify({'code': 3, 'error': 'no channel to close', 'res': 'lnd node closechannel'})

#example: https://127.0.0.1/checkchannel?pubkey=abc
@app.route('/checkchannel', methods=['GET'])
def checkchannel():

	pubkey = request.args.get('pubkey')
	
	if(not pubkey):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'lnd node checkchannel'})

	return jsonify(getchannel(pubkey))

def getchannel(pubkey):

	channels = listchannels()
	channels = json.loads(channels.data)
	if(len(channels) == 0):
		return channels
	else:
		channels = channels['channels']
		for channel in channels:
			if pubkey == channel['remote_pubkey']:
				return channel

	return {}	

@app.route('/listchannels', methods=['GET'])
def listchannels():

	channel_url = base_url + 'channels'

	try:
		r = requests.get(channel_url, headers=headers, verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node listchannels'})	
	
	return jsonify(r.json())

#example: https://127.0.0.1/invoice?amt=1000&memo=hi
@app.route('/invoice', methods=['GET'])
def invoice():

	amt = request.args.get('amt')
	memo = request.args.get('memo')
	
	if(not amt):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'lnd node invoice'})

	invoice_url = base_url + 'invoices'
	
	if(memo):
		data = {
			'memo':memo,
			'value':amt
		}
	else:
		data = {
			'value':amt
		}

	try:
		r = requests.post(invoice_url, headers=headers, verify=cert_path, data=json.dumps(data))
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node invoice'})	
	
	return jsonify(r.json())	

@app.route('/decodepayreq/<pay_req>', methods=['GET'])
def decodepayreq(pay_req):
	
	decode_url = base_url + 'payreq/' + pay_req

	try:
		r = requests.get(decode_url, headers=headers, verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node decodepayreq'})
	
	return jsonify(r.json())

#example: https://127.0.0.1/sendpayment?payreq=abc
@app.route('/sendpayment')
def sendPayment():

	pay_req = request.args.get('payreq')

	if(not pay_req):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'lnd node sendpayment'})
	
	#payment checking is being done on master node 
	tx_url = base_url + 'channels/transactions'

	data = {
		'payment_request': pay_req
	}

	try:
		r = requests.post(tx_url, headers=headers, verify=cert_path, data=json.dumps(data))
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'lnd node sendpayment'})
	

	return jsonify(r.json())

@app.route('/create', methods=['GET','POST'])
def create():

	ret_dict = {}

	wallet = initWallet()

	if("error" in wallet):
		return jsonify(wallet)

	pw = wallet["pw"]
	seed = wallet["seed"]

	time.sleep(5)

	address = initAddress()	
	if("error" in address):
		return jsonify(address)

	address = address["address"]

	ret_dict['password'] = pw
	ret_dict['seed'] = seed
	ret_dict['address'] = address

	return jsonify(ret_dict)


def generateBlocks(num):
	cmd = '/home/ec2-user/gocode/bin/btcctl --simnet --rpcuser=kek --rpcpass=kek --rpccert=/home/ec2-user/.lnd/rpc.cert --rpcserver=10.0.0.229:18556 generate ' + str(num)
	os.system(cmd)

#Helper Functions
def initLnd():
	
	#deprecated - now using systemd to spin up lnd
	lnd_cmd = "lnd --rpclisten=localhost:10001 --listen=localhost:10011 --restlisten=localhost:8001 --bitcoin.simnet --bitcoin.node=btcd\n"
	screen_lnd_cmd = "screen -S lndt -X stuff " + "\"" + lnd_cmd + "\""
	create_screen_cmd = "screen -dmS lndt"
	os.system(create_screen_cmd)
	os.system(screen_lnd_cmd)
	
	time.sleep(1)

def initWallet():
	
	#create wallet
	wallet_url = base_url + 'initwallet'
	pw = generate_pw()
	seed = generate_seed()
	if("error in seed"):
		return seed
	seed = seed["seed"]

	data = {
		'wallet_password': base64.b64encode(pw).decode(),
		'cipher_seed_mnemonic': seed	
	}

	try:
		r = requests.post(url, verify=cert_path, data=json.dumps(data))
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return {'code': 4, 'error': str(err), 'res': 'lnd node initwallet'}

	return {"pw":pw, "seed":seed}

def initAddress():
	
	#generate bitcoin address
	address_url = base_url + 'newaddress'

	try:
		r = requests.get(address_url, headers=headers, verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return {'code': 4, 'error': str(err), 'res': 'lnd node initaddress'}
	
	if('address' in r.json()):
		return {"address": r.json()['address']}
	else:
		return {'code': 3, 'error': 'could not generate address', 'res': 'lnd node initaddress'}

def generate_pw():
	
	#generate secure 8 character password
	chars = string.letters + string.digits + string.punctuation
	pw = ""
	for i in range(8):
		pw += random.choice(chars)
	print(pw)
	
	return pw

def generate_seed():

	#generate mnemonic seed for wallet
	seed_url = base_url + 'genseed'
  	
  	try:
		r = requests.get(seed_url,verify=cert_path)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return {'code': 4, 'error': str(err), 'res': 'lnd node initaddress'}
  	
  	if('cipher_seed_mnemonic' in r.json()):
		return {'seed': r.json()['cipher_seed_mnemonic']}
	else:
		return {'code': 3, 'error': 'could not generate address', 'res': 'lnd node initaddress'}

if __name__ == '__main__':
	app.run(port='5002')

