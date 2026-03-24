import requests
from bs4 import BeautifulSoup

url = "http://198.18.32.1/reg"#/php?ah_goal=index.html&ah_log=true"
payload = {"url":"E2B8F3578D88E9E372C8A715DED910CE976547C419","checkbox":"checkbox"}
headers = {"Content-type":"application/x-www-form-urlencoded"}

response = requests.post(url, data=payload, headers=headers)

if response.status_code == 200:
	soud = BeautifulSoup(response.text, "html.parser")
	
	print ("Connected to WiFi")
else:
	print(f"Resquest failed with status code {response.status_code}")
