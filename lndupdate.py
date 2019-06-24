from flask import Flask, request, jsonify
import os
import requests
import string
import random
import base64, codecs, json
import time


app = Flask(__name__)

@app.route('/update', methods=['GET', 'POST'])
def update():
	
	os.system('git pull origin master')
	os.system('sudo systemctl restart wsgi_lndserver')
	
	return "ok"

if __name__ == "__main__":
   app.run(host='0.0.0.0', port=5001)
