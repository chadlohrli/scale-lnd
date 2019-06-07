import os
import sys
import time
import json
import boto3
import requests
import uuid
import math
from google.cloud import firestore
from flask import Flask, request, jsonify

app = Flask(__name__)
db = firestore.Client()
aws_template_id = 'lt-0e8c7bf29b5bcc011' #lnd-create template
lnd_base_url = '/lnd/v1'

#create new lnd node
@app.route(lnd_base_url + 'create/<uuid>', methods=['GET'])
def create(uuid):

	#instantiante aws client
	client = boto3.client('ec2')

	#assume user is logged into fabrx to grab UUID,
	#in this case we generate a UUID for testing

	#node_id = 'lnd-' + str(uuid.uuid1())
	node_id = 'lnd-' + str(uuid);

	#check if this instance has already been created
	ec2_filters = [{
		'Name': 'tag:Name',
		'Values': [node_id]
	}]
	reservations = client.describe_instances(Filters=ec2_filters)

	if (len(reservations['Reservations']) != 0):
		return ("You already have a lnd node running!")

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
	time.sleep(60)
	lnd_server = 'http://' + instance_ref.public_dns_name + ':5000/create'
	r = requests.get(lnd_server)

	#3) save data to firebase
	doc_ref = db.collection(u'lnd').document(node_id)
	doc_ref.set({
		u'instance': {
			u'id' : unicode(instance_id),
			u'privateIP' : unicode(instance_private_ip),
			u'createTime' : unicode(instance_time),
		},
		u'wallet' : r.json(),
		u'timestamp' : firestore.SERVER_TIMESTAMP
		})

	return "Success!"

@app.route(lnd_base_url + 'getinfo/<uuid>', methods=['GET'])
def getinfo(uuid):

	url = getlndip(uuid) + 'getinfo'
	r = requests.get(url))

	return jsonify(r.json())

@app.route(lnd_base_url + 'walletbalance/<uuid>', methods=['GET'])
def walletbalance(uuid):
	
	url = getlndip(uuid) + 'walletbalance'
	r = requests.get(url)

	return jsonify(r.json())

# examples http://127.0.0.1/lnd/v1/pay?uuid=123&pubkey=abc&host=ip:port&amt=1000&payreq=lnabc&memo=hi
@app.route(lnd_base_url + 'pay', methods=['GET'])
def pay():
	
	uuid = request.args.get('uuid')
	pubkey = request.args.get('pubkey')
	host = request.args.get('host')
	chan_amt = request.args.get('amt')
	payreq = request.args.get('payreq')
	memo = request.args.get('memo')

	if(uuid or not pubkey or not host or not chan_amt or not payreq):
		return "Incorrect Format"

	base_url = getlndip(uuid) 

	#first we need to check funds
	wallet_balance = walletbalance(uuid)
	total_balance = wallet_balance['total_balance']	

	#get payment amount
	payreq_url = base_url + 'decodepayreq/' + payreq
	r = requests.get(payreq_url)
	pay_amt = r.json()['num_satoshis']
	
	#first we need to check if they are already connected
	connect_url = base_url + 'connect?pubkey=' + pubkey + '&' + host
	r = requests.get(connect_url)
	
	if(len(r.json()) !=0):
		err = r.json()['error'].split(':')[0]
		if(err != 'already connected to peer'):
			return 'Incorrect Public Key or Host'	

	#second we need to check if there is already a channel open
	checkchannel_url = base_url + 'checkchannel')
	r = requests.get(checkchannel_url)

	channel = r.json()

	if(len(channel) == 0):

		if(walletbalance < chan_amt):
			return "Not enough wallets funds"
		elif(math.floor(int(chan_amt)*0.8) < int(pay_amt)):
			return "Not enough channel funds"
	
		push_amt = math.floor(int(chan_amt)*0.2)
		chan_amt = int(chan_amt) - push_amt
		
		openchannel_url = base_url + 'openchannel?pubkey=' + pubkey + '&' + str(amt) + '&' + str(pushamt)
		r = requests.get(openchannel_url)
		res = r.json()
		if(!res['funding_txid_str']):
			return 'Issue Creating Channel'
	
	else:

		if(channel['local_balance'] < pay_amt):
			return "Not enough channel funds"
	

	#last we are ready for the payment
	pay_url = base_url + 'sendpayment?payreq=' + payreq
	r = requests.get(pay_url)

	if(r.json()['payment_hash]'):
		return "Success"
	else:
		return "Could not complete transaction"


@app.route(lnd_base_url + 'channelbalance/<uuid>', methods=['GET'])
def channelbalance(uuid):
	
	url = getlndip(uuid) + 'channelbalance'
	r = requests.get(url) 
	
	return jsonify(r.json())

def getlndip(uuid):

	node_id = 'lnd-' + str(uuid);
	doc_ref = db.collection(u'lnd').document(node_id)
	doc = doc_ref.get()
	instance_id = str(doc.to_dict()['instance']['id'])
	instance_ref = boto3.resource('ec2').Instance(instance_id)

	lnd_ip = 'http://' + instance_ref.public_dns_name + ':5000/'

	return lnd_ip	

@app.route('/test', methods=['GET'])
def testlnd():
	
	client = boto3.client('ec2')

	ec2_filters = [{
		'Name': 'tag:Name',
		'Values': ['lnd-test']
	}]

	reservations = client.describe_instances(Filters=ec2_filters)
	instance = reservations['Reservations'][0]['Instances'][0]
	instance_id = instance['InstanceId']
	
	instance_ref = boto3.resource('ec2').Instance(instance_id)

	instance_ref.start()
	instance_ref.wait_until_running()

	url = 'http://' + instance_ref.public_dns_name + ':5000/create'

	r = requests.get(url)

	
	doc_ref = db.collection(u'lnd').document('lnd-test1')
	doc_ref.set({
		u'wallet': r.json()
		})
	
	return str(r.json())



if __name__ == '__main__':
	app.run(port='5001')


