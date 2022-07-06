import gzip
import json
import numpy as np
import random 
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import paramiko
import uuid

def load_mid_config():
	with open("template_node_mid.json","r",encoding="utf-8") as fh:
		return json.loads(fh.read())

def load_last_config():
	with open("template_node_last.json","r",encoding="utf-8") as fh:
		return json.loads(fh.read())

def para_init(host,port,user,pwd):
	trans = paramiko.Transport((host, port))
	trans.connect(username=user, password=pwd)
	return trans

def para_init_key(host,port,user,key):
	trans = paramiko.Transport((host,port))
	private_key = paramiko.RSAKey.from_private_key_file(key)
	trans.connect(username=user,pkey=private_key)
	return trans

def ssh_single_cmd(trans,cmd):
	ssh = paramiko.SSHClient()
	ssh._transport = trans
	stdin, stdout, stderr = ssh.exec_command(cmd)
	result = stdout.read().decode()
	return result

def sftp_connect(trans):
	sftp = paramiko.SFTPClient()
	sftp.from_transport(trans)
	return sftp

def detour_graph(edge_list,a,b):
	#swap node a and b
	for j in range(len(edge_list)):
		if(edge_list[j] == a):
			edge_list[j] = -1
		if(edge_list[j] == b):
			edge_list[j] = a
	for j in range(len(edge_list)):
		if(edge_list[j] == -1):
			edge_list[j] = b

def generate_random_edge_list(count):
	edge_list = []
	for j in range(count):
		edge_list.append(j)
		edge_list.append((j+1)%count)
	for j in range(int(count/2)+1):
		a = random.randrange(count)
		b = random.randrange(count)
		detour_graph(edge_list,a,b)
	return edge_list
def main():
	config_file = open("config.json",'r')
	loaded_config = json.load(config_file)
	loaded_server = loaded_config['servers']
	server_count = len(loaded_server)
	for j in range(server_count):
		loaded_server[j]['uuid'] = str(uuid.uuid4())
	edge_list = generate_random_edge_list(server_count)

	from_list = []
	to_list=[]
	for j in range(server_count):
		#FROM = edge_list[j*2]
		#TO   = edge_list[j*2+1]
		#Routing_dict['']
		to_composite = {"host":loaded_server[edge_list[j*2+1]]['host'],
			"port":loaded_server[edge_list[j*2+1]]['port'],
			"uuid":loaded_server[edge_list[j*2+1]]['uuid'],
		}
		loaded_server[edge_list[j*2]]['to_composite'] = to_composite

		from_list.append(str(edge_list[j*2]))
		if(edge_list[j*2+1] != 0):
			to_list.append(str(edge_list[j*2+1]))
		else:
			to_list.append(str(edge_list[j*2]))
			
	df = pd.DataFrame({ 'from':from_list, 'to':to_list})
	# Build your graph
	G=nx.from_pandas_edgelist(df, 'from', 'to',create_using=nx.DiGraph())
	print(edge_list)
	nx.draw(G, with_labels=True, node_size=300, font_size=10, font_color="black", font_weight="bold",pos=nx.circular_layout(G))
	plt.show()

	for node in loaded_server:
		print("Configurating node "+node['alias'])
		node_config = {}

		if(node['is_using_key_file'] == False):
			node['Transport'] = para_init(node['host'],22,node['user'],node['password'])
		else:
			node['Transport'] = para_init_key(node['host'],22,node['user'],node['key_file'])

		res = ssh_single_cmd(node['Transport'],"ls /etc/v2ray/")

		if("config.json" in res):
			#Already Installed
			print("Already Installed")
		else:
			ssh_single_cmd(node['Transport'],"bash <(curl -sL https://raw.githubusercontent.com/hijkpw/scripts/master/goV2.sh)")
			print("Newly Installed")

		#START PREPARING CONFIG
		prepared_dict = {}
		if node['to_composite']['host'] == loaded_server[0]['host']:
			#LAST NODE
			prepared_dict = load_last_config()
			prepared_dict['inbounds'][0]['port'] = int(node['port'])
			prepared_dict['inbounds'][0]['settings']['clients'][0]['id'] = node['uuid']
		else:
			#MID  NODE
			prepared_dict = load_mid_config()
			prepared_dict['inbounds'][0]['port'] = int(node['port'])
			prepared_dict['inbounds'][0]['settings']['clients'][0]['id'] = node['uuid']

			prepared_dict['outbounds'][0]['settings']['vnext'][0]['address'] = node['to_composite']['host']
			prepared_dict['outbounds'][0]['settings']['vnext'][0]['port'] = int(node['to_composite']['port'])
			prepared_dict['outbounds'][0]['settings']['vnext'][0]['users'][0]['id'] = node['to_composite']['uuid']

		node['completed_config'] = prepared_dict
		completed_config = json.dumps(node['completed_config'])
		#END PREPARING CONFIG
		print(completed_config)
		with sftp_connect(node['Transport']).file("/etc/v2ray/config.json","w") as config_file:
			config_file.write(completed_config)
		
		ssh_single_cmd(node['Transport'],"ufw allow 1081")
		ssh_single_cmd(node['Transport'],"ufw allow 1082")
		ssh_single_cmd(node['Transport'],"ufw allow "+node['port'])
		ssh_single_cmd(node['Transport'],"ufw allow "+node['to_composite']['port'])
		ssh_single_cmd(node['Transport'],"systemctl enable v2ray")
		ssh_single_cmd(node['Transport'],"systemctl start v2ray")

#check install
#"bash <(curl -sL https://raw.githubusercontent.com/hijkpw/scripts/master/goV2.sh)"
#write config
#ufw allow
#systemctl enable v2ray
#systemctl start v2ray

if __name__=="__main__":
    main()