import requests

def httpRequest(url,params,user,password):
    authentication = requests.auth.HTTPBasicAuth(user,password)
    response = requests.get(url=url,auth=authentication,params=params)
    if not (response.status_code > 199 and response.status_code < 300):
        print("INVALID RESPONSE")
        return None
    return response