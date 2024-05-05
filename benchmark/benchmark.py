
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import requests
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PREFIX = "/api/test"
DEFAULT_RESULTS = "results/"
DEFAULT_ADMIN_TOKEN = ""

DEFAULT_AVERAGE_TIME = True
DEFAULT_AVERAGE_ENDPOINT = True
DEFAULT_AVERAGE_METHOD = True
DEFAULT_CALL_TIME = True
    
SEQUENCE = "sequence"
PARALLEL = "parallel"
ENDPOINT = "endpoint"
HOST = "host"
METHOD = "method"
BODY = "body"
HEADERS = "headers"
RESPONSE = "response"
EXPECTED_STATUS = "expected_status"
   
ADMIN_TOKEN = "admin_token"

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
   
responses = {}
benchmark_results = {}
 
def register_benchmark(endpoint, method, time, status, status_expected):
    
    if endpoint not in benchmark_results:
        benchmark_results[endpoint] = []
    
    benchmark_results[endpoint].append({"method": method, "time": time, "status": status, "status_expected": status_expected if status_expected else "-", "ok": (status == status_expected) if status_expected else True})
    
def make_request(method, endpoint, body, headers):
    start_time = time.time()
    response = requests.request(method, endpoint, json=body, headers=headers)
    end_time = time.time()
    duration = end_time - start_time
    return response.json(), response.status_code, duration
    
def make_test_call(test):
    
    response, status, duration = make_request(test[METHOD], test[HOST] + test[ENDPOINT], test[BODY], test[HEADERS])
    
    if test[RESPONSE] is not None:
        responses[test[RESPONSE]] = response
        
    register_benchmark(test[ENDPOINT], test[METHOD], duration, status, test[EXPECTED_STATUS])    
    
    return response, status, duration
    
def check_and_create_folder(folder):
    folders = folder.split('/')
    
    for i in range(1, len(folders) + 1):
        path = './'.join(folders[:i])
        if not os.path.exists(path):
            os.mkdir(path)
  
def get_value(response, vars):
    if len(vars) == 1:
        return response[vars[0]]
    else:
        return get_value(response[vars[0]], vars[1:])
    
def compile_string(string: str, admin_token: str):
    
    string_result = string.replace(f"{{{ADMIN_TOKEN}}}", admin_token)
    
    exp = r'\{(.*?)\}'
    
    var_names = re.findall(exp, string_result)
    
    for var in var_names:
        vars = var.split('.')
        
        if vars[0] not in responses:
            raise Exception(f"Variable {vars[0]} not found in responses.")
        
        response = responses[vars[0]]
        
        value = get_value(response, vars[1:])
        
        string_result = string_result.replace(f"{{{var}}}", value)
    
    return string_result
    
def get_data_call(host, admin_token: str, test):
    
    test[ENDPOINT] = compile_string(test[ENDPOINT], admin_token)
    
    if HOST not in test: test[HOST] = host
    if METHOD not in test: test[METHOD] = "GET"
    if BODY not in test: test[BODY] = {}
    if HEADERS not in test: test[HEADERS] = {}
    if RESPONSE not in test: test[RESPONSE] = None
    if EXPECTED_STATUS not in test: test[EXPECTED_STATUS] = None
    
    for key in test[BODY]:
        test[BODY][key] = compile_string(test[BODY][key])
        
    for key in test[HEADERS]:
        test[HEADERS][key] = compile_string(test[HEADERS][key])
        
    test[METHOD] = test[METHOD].upper()
        
    return test
    
def sequence(host: str, admin_token: str, tests: list):
    for t in tests:
        test(host, t)

def parallel(host: str, admin_token: str, tests: dict):
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(test, host, admin_token, t) for t in tests]
        
    for future in futures:
        future.result()
    
def test(host: str, admin_token: str, test: dict):
    
    if SEQUENCE in test: sequence(host, admin_token, test[SEQUENCE])
    if PARALLEL in test: parallel(host, admin_token, test[PARALLEL])
    if ENDPOINT in test:
        
        test = get_data_call(host, admin_token, test)
        make_test_call(test)
    
def benchmark(host: str, admin_token: str, results_path: str, tests: dict, register_average_time: bool, register_average_endpoint: bool, register_average_method: bool, register_call_time: bool):
    
    test(host, admin_token, tests)
    

def main():
    
    parser = argparse.ArgumentParser(description='Test of performance to booking API.')

    parser.add_argument('--host', default=DEFAULT_HOST, type=str, help='Host to connect.')
    parser.add_argument('--prefix', default=DEFAULT_PREFIX, type=str, help='API endpoint prefix.')
    parser.add_argument('--results', default=DEFAULT_RESULTS, type=str, help='Results folder.')
    parser.add_argument('--test-file', required=True, type=str, help='Test file to run.')
    parser.add_argument('--admin-token', default=DEFAULT_ADMIN_TOKEN, type=str, help='Admin token to access the API.')
    parser.add_argument('--register-average-time', default=DEFAULT_AVERAGE_TIME, type=bool, help='Average time of test.')
    parser.add_argument('--register-average-endpoint', default=DEFAULT_AVERAGE_ENDPOINT, type=bool, help='Average time of each endpoint.')
    parser.add_argument('--register-average-method', default=DEFAULT_AVERAGE_METHOD, type=bool, help='Average time of each method.')
    parser.add_argument('--register-call-time', default=DEFAULT_CALL_TIME, type=bool, help='Time of each call.')

    args = parser.parse_args()
    
    file = args.test_file
    
    content_json = None
    
    with open(file, 'r') as file:
        content = file.read()
        try:
            content_json = json.loads(content)
        except json.JSONDecodeError as e:
            print(f'Error: {e}')
            return
        
    check_and_create_folder(args.results)
        
    print("Starting benchmark...\n")
    benchmark(args.host + args.prefix, args.admin_token, args.results, content_json, args.register_average_time, args.register_average_endpoint, args.register_average_method, args.register_call_time)
    print("\nBenchmark finished.")

if __name__ == '__main__':
    main()