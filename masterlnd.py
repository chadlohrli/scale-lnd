import os
import sys
import time
import json
import boto3
import requests
import uuid
from google.cloud import firestore
from flask import Flask, request, jsonify

app = Flask(__name__)
db = firestore.Client()
aws_template_id = 'lt-0e8c7bf29b5bcc011' #lnd-create template
#api_version = 'v1'

#create new lnd node
@app.route('/v1/create/<uuid>', methods=['GET','POST'])
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

@app.route('/v1/getinfo/<uuid>')
def getinfo(uuid):

	node_id = 'lnd-' + str(uuid);
	doc_ref = db.collection(u'lnd').document(node_id)
	doc = doc_ref.get()
	instance_id = str(doc.to_dict()['instance']['id'])
	instance_ref = boto3.resource('ec2').Instance(instance_id)

	lnd_server = 'http://' + instance_ref.public_dns_name + ':5000/getinfo'
	r = requests.get(lnd_server)
	return(str(r.json()))



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


