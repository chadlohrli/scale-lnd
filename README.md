# scale-lnd
Proof of concept for automatically creating [lnd](https://github.com/lightningnetwork/lnd) nodes at a user level and managing them via a master node.

Notes:
* Operational but with specifically set up EC2 instances **(TODO -- publish templates)** 
* Uses simnet

Tools Used:
* LND - Lightning Network Daemon
* BTCD - Bitcoin Daemon
* BOTO3 - AWS EC2 Instantiation
* Firebase - Storing User/Node Information

### High Level Architecture
![architecture](/assets/architecture.jpg)

---

### Create API Diagram
![create](/assets/create.jpg)

---

### Master Node API
* `POST /lnd/v1/update` - listens for github webhook & updates all lndserver nodes   
* `GET /lnd/v1/create` - creates a lndserver node using AWS EC2 and saves credentials on Firebase  
  *example:* **/create?uuid=123**
* `GET /lnd/v1/getinfo` - gets lnd node info from lndserver  
  *example:* **/getinfo?uuid=123**
* `GET /lnd/v1/walletbalance` - gets wallet balance from lndserver    
  *example:* **/walletbalance?uuid=123**
* `GET /lnd/v1/channelbalance` - gets channel balance from lndserver    
  *example:* **/channelbalance?uuid=123** 
* `GET /lnd/v1/listchannels`  - list all channels from lndserver   
  *example:* **/listchannels?uuid=123**
* `GET /lnd/v1/closechannel` - closes a channel with a specific public key (user)  
  *example:* **/closechannel?uuid=123&pubkey=abc**    
* `GET /lnd/v1/listpeers` - lists peers via public keys  
  *example:* **/listpeers?uuid=123**     
* `GET /lnd/v1/deletepeer` - deletes a user via public key  
  *example:* **/deletepeer?uuid=123&pubkey=abc**   
* `GET /lnd/v1/invoice` - returns a payment request   
  *example:* **/invoice?uuid=123&amt=10000&memo=hi** 
* `GET /lnd/v1/pay` - send a payment   
  * pay will automatically open a channel and fund it if it does not exist  
  *example:* **/pay?uuid=123&pubkey=abc&host=ip:port&amt=1000&payreq=lnabc**
  
---

**TODO**
- Make API more robust
- Publish 'how to use' documentation
  * how to set up BTCD, AWS, & Firebase
- Clean up and publish AWS EC2 templates for *masterlnd* & *lndserver*
- Use Asyncio
- Move from simnet -> testnet -> mainnet?
