import os
import sys
import time
import json
import boto3
import requests
import uuid
import math
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from flask import Flask, request, jsonify

app = Flask(__name__)
cred = credentials.Certificate("./firebase_auth.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
aws_template_id = 'lt-099f669346f789bc2' #lnd-create template
lnd_base_url = '/lnd/v1/'

@app.route('/test')
def test():
	return "hello world"

#create new lnd node
@app.route(lnd_base_url + 'create/<uuid>', methods=['GET'])
def create(uuid):

	#instantiante aws client
	client = boto3.client('ec2')

	#node_id = 'lnd-' + str(uuid.uuid1())
	node_id = 'lnd-' + str(uuid);

	#check if this instance has already been created
	ec2_filters = [{
		'Name': 'tag:Name',
		'Values': [node_id]
	}]
	reservations = client.describe_instances(Filters=ec2_filters)

	if (len(reservations['Reservations']) != 0):
		return jsonify({'code': 3, 'error': 'You already have a lnd node running!', 'res': 'master lnd node create'})

	#1) spin up aws instance from lnd template image
	instance = client.run_instances(
		LaunchTemplate = {
			'LaunchTemplateId': aws_template_id
		},
		TagSpecifications = [{
			'ResourceType':'instance',
			'Tags':[{'Key':'Name', 'Value': node_id}]
		}],
		MaxCount=1,
		MinCount=1
	)

	# grab new instance params
	instance_id = instance['Instances'][0]['InstanceId']
	instance_private_ip = instance['Instances'][0]['PrivateIpAddress']
	instance_ref = boto3.resource('ec2').Instance(instance_id)

	# wait until instance is created before moving on (TODO: error checking & front-end loading bar)
	start = time.time()
	instance_ref.wait_until_running()
	end = time.time()
	instance_time = end - start

	#2) create wallet on lnd server
	time.sleep(20)
	lnd_server = 'http://' + instance_ref.public_dns_name + ':5000/create'

	try:
		r = requests.get(lnd_server)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node create (init'})		

	wallet = r.json()
	if("error" in wallet):
		return jsonify(wallet)

	#3) grab public key
	get_info_url = 'http://' + instance_ref.public_dns_name + ':5000/getinfo'
	try:
		r = requests.get(get_info_url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node create (getinfo)'})
	
	pubkey = r.json()
	if("error" in pubkey):
		return jsonify(pubkey)

	pubkey = pubkey['identity_pubkey']
	
	# *At this point we can assume no errors, so let's save to firebase*

	#4) save data to firebase
	doc_ref = db.collection(u'lnd').document(node_id)
	doc_ref.set({
		u'instance': {
			u'id' : unicode(instance_id),
			u'privateIP' : unicode(instance_private_ip),
			u'createTime' : unicode(instance_time),
		},
		u'lndnode':{
			u'host' : unicode(instance_private_ip),
			u'port' : unicode("10011"),
			u'pubkey': unicode(pubkey),
			u'wallet' : wallet,
		},
		u'timestamp' : firestore.SERVER_TIMESTAMP
	})

	#4) send intial coins
	address = wallet['address']
	lncmd = '/home/ec2-user/gocode/bin/lncli --rpcserver=localhost:10001 --macaroonpath=data/chain/bitcoin/simnet/admin.macaroon'
	snd = ' sendcoins --addr=' + address + ' ' + '--amt=100000000'
	cmd = lncmd + snd
	os.system(cmd)

	return jsonify({'code': 5, 'success': True, 'res': 'master lnd node create (finalize init)'})

'''
@app.route(lnd_base_url + 'unlock/<uuid>', methods=['GET'])
def unlock(uuid):

	node_id = 'lnd-' + str(uuid);
	doc_ref = db.collection(u'lnd').document(node_id)
	doc = doc_ref.get()
	if(not doc.to_dict()):
		return jsonify({'code': 3, 'error': 'user does not exist', 'res': 'master lnd node unlock'})

	password = str(doc.to_dict()['wallet']['password'])

	return password
'''

@app.route(lnd_base_url + 'getinfo/<uuid>', methods=['GET'])
def getinfo(uuid):

	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)
	
	url = url + 'getinfo'

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node getinfo'})
	
	return jsonify(r.json())

@app.route(lnd_base_url + 'walletbalance/<uuid>', methods=['GET'])
def walletbalance(uuid):
	
	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)

	url = url + 'walletbalance'

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node walletbalance'})

	return jsonify(r.json())

@app.route(lnd_base_url + 'channelbalance/<uuid>', methods=['GET'])
def channelbalance(uuid):
	
	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)
	
	url = url + 'channelbalance'

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node channelbalance'})
	
	return jsonify(r.json())

@app.route(lnd_base_url + 'listchannels/<uuid>', methods=['GET'])
def listchannels(uuid):

	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)

	url = url + 'listchannels'

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node walletbalance'})

	return jsonify(r.json())

#example: https://127.0.0.1/closechannel?uuid=123&pubkey=abc
@app.route(lnd_base_url + 'closechannel', methods=['GET'])
def closechannel():

	pubkey = request.args.get('pubkey')
	uuid = request.args.get('uuid')

	if(not uuid or not pubkey):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'master lnd node closechannel'})

	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)
		
	url = url + 'closechannel?pubkey=' + pubkey

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node closechannel'})

	return jsonify(r.json())

@app.route(lnd_base_url + 'listpeers/<uuid>', methods=['GET'])
def listpeers(uuid):

	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)

	url = url + 'peers'

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node listpeers'})

	return jsonify(r.json())


# examples http://127.0.0.1/lnd/v1/addpeer?uuid=123&pubkey=abc&host=ip:port
@app.route(lnd_base_url + 'addpeer', methods=['GET'])
def addpeer():

	uuid = request.args.get('uuid')
	pubkey = request.args.get('pubkey')
	host = request.args.get('host')

	if(not uuid or not pubkey or not host):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'master lnd node addpeer'})

	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)

	url = url + 'connect?pubkey=' + pubkey + '&host=' + host

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node connect'})

	return jsonify(r.json())

#example: https://127.0.0.1/closechannel?uuid=123&pubkey=abc
@app.route(lnd_base_url + 'deletepeer', methods=['GET'])
def deletepeer():

	uuid = request.args.get('uuid')
	pubkey = request.args.get('pubkey') 

	if(not uuid or not pubkey):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'master lnd node deletepeer'})

	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)

	url = url + 'deletepeer?pubkey=' + pubkey

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node deletepeers'})

	return jsonify(r.json())


# example http://127.0.0.1/lnd/v1/invoice?uuid=123&amt=10000&memo=hi
@app.route(lnd_base_url + 'invoice', methods=['GET'])
def invoice():

	uuid = request.args.get('uuid')
	amt = request.args.get('amt')
	memo = request.args.get('memo')

	if(not uuid or not amt):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'master lnd node invoice'})

	url = getlndip(uuid)
	if('error' in url):
		return jsonify(url)

	url = url + 'invoice?amt=' + amt

	if(memo):
		url = url + '&memo=' + memo

	try:
		r = requests.get(url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node invoice'})

	return(jsonify(r.json()))

# examples http://127.0.0.1/lnd/v1/pay?uuid=123&pubkey=abc&host=ip:port&amt=1000&payreq=lnabc
@app.route(lnd_base_url + 'pay', methods=['GET'])
def pay():
	
	uuid = request.args.get('uuid')
	pubkey = request.args.get('pubkey')
	host = request.args.get('host')
	chan_amt = request.args.get('amt')
	payreq = request.args.get('payreq')

	if(not uuid or not pubkey or not host or not chan_amt or not payreq):
		return jsonify({'code': 3, 'error': 'invalid request format', 'res': 'master lnd node pay'})

	base_url = getlndip(uuid) 
	if('error' in base_url):
		return jsonify(base_url)

	#first we need to check funds
	wallet_balance = walletbalance(uuid).get_json() #note this returns a response
	
	if("error" in wallet_balance):
		return jsonify(wallet_balance)

	total_balance = wallet_balance['total_balance']	

	#get payment amount
	payreq_url = base_url + 'decodepayreq/' + payreq
	
	try:
		r = requests.get(payreq_url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node pay (decodepayreq)'})
	
	if('num_satoshis' in r.json()):
		pay_amt = r.json()['num_satoshis']
	else:
		return(jsonify(r.json()))

	#first we need to check if they are already connected
	connect_url = base_url + 'connect?pubkey=' + pubkey + '&host=' + host

	try:
		r = requests.get(connect_url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node pay (connect)'})

	if(len(r.json()) !=0):
		err = r.json()['error'].split(':')[0]
		if(err != 'already connected to peer'):
			return jsonify(r.json())

	#second we need to check if there is already a channel open
	checkchannel_url = base_url + 'checkchannel?pubkey=' + pubkey

	try:
		r = requests.get(checkchannel_url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node pay (checkchannel)'})
	
	channel = r.json()

	if(len(channel) == 0):

		chan_amt = int(chan_amt) #channel funding 
		total_balance = int(total_balance) #total wallet balance
		pay_amt = int(pay_amt) #payment amount

		#return("chan amt:" + str(int(math.floor(chan_amt*0.8))) + " " + "pay_amt:" + str(pay_amt))

		if(total_balance < chan_amt):
			return jsonify({"code":"3","error":"Not enough wallets funds"})
		elif(int(math.floor(chan_amt*0.9)) < pay_amt):
			return jsonify({"code":"3","error":"Not enough channel funds"})
	
		push_amt = int(math.floor(chan_amt*0.1))
		chan_amt = chan_amt - push_amt

		#return("chan amt:" + str(chan_amt) + " " + "push_amt:" + str(push_amt))
		
		openchannel_url = base_url + 'openchannel?pubkey=' + pubkey + '&amt=' + str(chan_amt) + '&pushamt=' + str(push_amt)

		try:
			r = requests.get(openchannel_url)
			r.raise_for_status()
		except requests.exceptions.RequestException as err:
			return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node pay (openchannel)'})
		
		if('funding_txid_bytes' not in r.json()):
			return jsonify(r.json())
	
	else:
		chan_balance = int(channel['local_balance'])

		if(chan_balance < int(pay_amt)):
			return jsonify({"code":"3","error":"Not enough channel funds"})
	
	#last we are ready for the payment
	pay_url = base_url + 'sendpayment?payreq=' + payreq
	time.sleep(1) #give time to mine open channel tx
	try:
		r = requests.get(pay_url)
		r.raise_for_status()
	except requests.exceptions.RequestException as err:
		return jsonify({'code': 4, 'error': str(err), 'res': 'master lnd node pay (sendpayment)'})

	return(jsonify(r.json()))

#@app.route(lnd_base_url + 'genblocks/<num>', methods=['GET'])
def generateBlocks(num):
	cmd = '/home/ec2-user/gocode/bin/btcctl --simnet --rpcuser=kek --rpcpass=kek generate ' + str(num)
	os.system(cmd)

def getlndip(uuid):

	node_id = 'lnd-' + str(uuid);
	doc_ref = db.collection(u'lnd').document(node_id)
	doc = doc_ref.get()
	if(not doc.to_dict()):
		return {'code': 3, 'error': 'user does not exist', 'res': 'master lnd node getip'}

	instance_id = str(doc.to_dict()['instance']['id'])
	instance_ref = boto3.resource('ec2').Instance(instance_id)

	lnd_ip = 'http://' + instance_ref.public_dns_name + ':5000/'

	return lnd_ip	

if __name__ == '__main__':
	app.run(port='5001')
