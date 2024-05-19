
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
DEFAULT_TEST_FILE = "test.json"

DEFAULT_AVERAGE_TIME = True
DEFAULT_AVERAGE_ENDPOINT = True
DEFAULT_AVERAGE_METHOD = True
DEFAULT_CALL_TIME = True

DEFAULT_ALERT_TIME = 4
DEFAULT_CHART_SECONDS = -1
DEFAULT_CHART_TOP_ENDPOINTS = 4
DEFAULT_CHART = True
    
SEQUENCE = "sequence"
PARALLEL = "parallel"
ENDPOINT = "endpoint"
HOST = "host"
METHOD = "method"
TITLE = "debug_comment"
ENABLED = "enabled"
BODY = "body"
HEADERS = "headers"
RESPONSE = "response"
EXPECTED_STATUS = "expected_status"
START = "start"
END = "end"
N = "n"
VARS = "vars"
FUNCTION_PREFIX = "__"
   
ADMIN_TOKEN = "ADMIN_TOKEN"
HOST = "HOST"

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]

JSON_FILE_NAME = "results.json"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
}

functions = {
    "concat": lambda *args: ''.join(args),
}

variables = {}
benchmark_results = {}
admin_token_value = None
host_value = None
 
def save_results_json(results_path, results):
    with open(results_path, 'w') as file:
        json.dump(results, file, indent=4)
 
def process_results(results_path):
    
    average_results = {}
    
    for endpoint in benchmark_results:
        total_time = 0.0
        total_calls = 0
        
        total_correct_status = 0
        total_incorrect_status = 0
        total_checked_status = 0
        
        results_method = {}
        
        for result in benchmark_results[endpoint]:
            total_time += result["time"]
            total_calls += 1
            
            results_method[result["method"]] = {
                "total_time": results_method[result["method"]]["total_time"] + result["time"] if result["method"] in results_method else result["time"],
                "total_calls": results_method[result["method"]]["total_calls"] + 1 if result["method"] in results_method else 1
            }
            
            if result["status_expected"] != "-":
                total_checked_status += 1
                
                results_method[result["method"]]["total_checked_status"] = results_method[result["method"]]["total_checked_status"] + 1 if result["method"] in results_method else 1
                
                if result["ok"]:
                    total_correct_status += 1
                    results_method[result["method"]]["total_correct_status"] = results_method[result["method"]]["total_correct_status"] + 1 if result["method"] in results_method else 1

                else:
                    total_incorrect_status += 1
                    results_method[result["method"]]["total_incorrect_status"] = results_method[result["method"]]["total_incorrect_status"] + 1 if result["method"] in results_method else 1
                
        average_time = float(total_time) / total_calls
        percent_correct_status = (float(total_correct_status) / total_checked_status) * 100 if total_checked_status > 0 else 100
        percent_incorrect_status = (float(total_incorrect_status) / total_checked_status) * 100 if total_checked_status > 0 else 0
        
        average_method = {}
        
        for method in results_method:
            average_method[method] = {
                "average_time": float(results_method[method]["total_time"]) / results_method[method]["total_calls"],
                "percent_correct_status": (float(results_method[method]["total_correct_status"]) / results_method[method]["total_checked_status"]) * 100 if results_method[method]["total_checked_status"] > 0 else 100,
                "percent_incorrect_status": (float(results_method[method]["total_incorrect_status"]) / results_method[method]["total_checked_status"]) * 100 if results_method[method]["total_checked_status"] > 0 else 0,
                "total_calls": results_method[method]["total_calls"],
                "total_checked_status": results_method[method]["total_checked_status"],
                "total_correct_status": results_method[method]["total_correct_status"],
                "total_incorrect_status": results_method[method]["total_incorrect_status"]
            }
            
        average_results[endpoint] = {
            "average_time": average_time,
            "percent_correct_status": percent_correct_status,
            "percent_incorrect_status": percent_incorrect_status,
            "total_calls": total_calls,
            "total_checked_status": total_checked_status,
            "total_correct_status": total_correct_status,
            "total_incorrect_status": total_incorrect_status,
            "average_method": average_method
        }
        
    file_name = JSON_FILE_NAME
    
    results_path = os.path.join(results_path, file_name)
        
    save_results_json(results_path, average_results)
 
def register_benchmark(endpoint, method, time, status, status_expected):
    
    if endpoint not in benchmark_results:
        benchmark_results[endpoint] = []
    
    benchmark_results[endpoint].append({"method": method, "time": time, "status": status, "status_expected": status_expected if status_expected else "-", "ok": (status == status_expected) if status_expected else True})
    
def make_request(method, endpoint, body, headers, retries=5):
    
    for i in range(retries):
        try:
            start_time = time.time()
            response = requests.request(method, endpoint, json=body, headers=headers)
            end_time = time.time()
            duration = end_time - start_time
            break
        except Exception as e:
            if i == retries - 1:
                raise e
            print(f"Retrying...")

    return (response.json() if response.status_code != 204 else {}), response.status_code, duration
    
def make_test_call(test):
    
    response, status, duration = make_request(test[METHOD], test[HOST] + test[ENDPOINT], test[BODY], test[HEADERS])
    
    if test[RESPONSE] is not None:
        variables[test[RESPONSE]] = response
        
    register_benchmark(test[ENDPOINT], test[METHOD], duration, status, test[EXPECTED_STATUS])    
    
    print(f"\n{test[TITLE]}\n{test[METHOD]} {test[ENDPOINT]} - {status} ... {duration} seconds. Expected: {test[EXPECTED_STATUS] if test[EXPECTED_STATUS] else '-'}\nBODY:\n\t{test[BODY]}\nHEADERS:\n\t{test[HEADERS]}\nRESPONSE:\n\t{response}")
    
    return response, status, duration
    
def check_and_create_folder(folder):
    folders = folder.split('/')
    
    for i in range(1, len(folders) + 1):
        path = './'.join(folders[:i])
        if not os.path.exists(path):
            os.mkdir(path)
  
def get_value(response, vars):
    index = int(vars[0]) if vars[0].isnumeric() else vars[0]
    if len(vars) == 1:
        
        if index not in response:
            print(f"Index {index} not found in response {response}.")
            return ""
        
        return response[index]
    else:
        return get_value(response[index], vars[1:])
    
def extract_braced_content(s):
    stack = []
    results = []
    l_brace, r_brace = '{', '}'
    start_idx = None

    for i, char in enumerate(s):
        if char == l_brace:
            if not stack:
                start_idx = i
            stack.append(l_brace)
        elif char == r_brace and stack:
            stack.pop()
            if not stack:
                results.append(s[start_idx + 1:i])
                
    return results
    
def compile_string(string: str|dict|list):
    
    if isinstance(string, dict):
        return {key: compile_string(string[key]) for key in string}
    
    if isinstance(string, list):
        return [compile_string(value) for value in string]
    
    if not isinstance(string, str):
        return string
    
    def process_function(var):
        function = var[len(FUNCTION_PREFIX):]
        function_name = function.split('(')[0]
        function_args = function.split('(')[1].split(')')[0].split(',')
        function_args = [compile_string(arg) for arg in function_args] 
    
        if function_name not in functions:
            raise Exception(f"Function {function_name} not found.")
        
        return functions[function_name](*function_args)
        
    string_result = string.replace(f"{{{ADMIN_TOKEN}}}", admin_token_value)
    
    var_names = extract_braced_content(string_result)
    
    for var in var_names:
                
        if var.startswith(FUNCTION_PREFIX):
            value = process_function(var)
        else:
            vars = var.split('.')
            
            if vars[0] not in variables:
                raise Exception(f"Variable {vars[0]} not found in responses.")
            
            response = variables[vars[0]]
            
            value = get_value(response, vars[1:]) if len(vars) > 1 else response
        
        string_result = string_result.replace(f"{{{var}}}", str(value))
    
    return string_result
    
def get_data_call(test):
    
    test[ENDPOINT] = compile_string(test[ENDPOINT])
    
    if HOST not in test: test[HOST] = host_value
    if METHOD not in test: test[METHOD] = "GET"
    if TITLE not in test: test[TITLE] = ""
    if BODY not in test: test[BODY] = {}
    if HEADERS not in test: test[HEADERS] = DEFAULT_HEADERS
    if RESPONSE not in test: test[RESPONSE] = None
    if EXPECTED_STATUS not in test: test[EXPECTED_STATUS] = None
    
    if type(test[BODY]) is list:
        
        body = []
        
        for b in test[BODY]:
            
            if type(b) is dict:
                body.append({key: compile_string(b[key]) for key in b})
            else:
                body.append(compile_string(b))
                
        test[BODY] = body
        
    else:
        for key in test[BODY]:
            test[BODY][key] = compile_string(test[BODY][key])
        
    for key in test[HEADERS]:
        test[HEADERS][key] = compile_string(test[HEADERS][key])
        
    test[METHOD] = test[METHOD].upper()
        
    return test
    
def set_vars(vars: dict):
    global admin_token_value
    global host_value
    
    for key in vars:
        
        if key == ADMIN_TOKEN: admin_token_value = compile_string(vars[key])
        elif key == HOST: host_value = compile_string(vars[key])
        else:
            variables[key] = compile_string(vars[key])
    
def sequence(tests: list):
    for t in tests:
        test(t)

def parallel(tests: dict):
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(test, t) for t in tests]
        
    for future in futures:
        future.result()
    
def test(test_conf: dict):
    
    if ENABLED in test_conf and not test_conf[ENABLED]: return
    
    n = test_conf[N] if N in test_conf else 1
    
    for _ in range(n):
        
        if VARS in test_conf: set_vars(test_conf[VARS])
        if START in test_conf: test(test_conf[START])
        if SEQUENCE in test_conf: sequence(test_conf[SEQUENCE])
        if PARALLEL in test_conf: parallel(test_conf[PARALLEL])
        if ENDPOINT in test_conf:
            test_conf = get_data_call(test_conf)
            make_test_call(test_conf)
        if END in test_conf: test(test_conf[END])
    
def benchmark(results_path: str, tests: dict, register_average_time: bool, register_average_endpoint: bool, register_average_method: bool, register_call_time: bool, alert_time: int, chart: bool, chart_seconds: int):
    
    test(tests)
    
    print("\nProcessing results...")
    
    process_results(results_path)

def main():
    
    parser = argparse.ArgumentParser(description='Test of performance to booking API.')

    parser.add_argument('--host', default=DEFAULT_HOST, type=str, help='Host to connect.')
    parser.add_argument('--prefix', default=DEFAULT_PREFIX, type=str, help='API endpoint prefix.')
    parser.add_argument('--results', default=DEFAULT_RESULTS, type=str, help='Results folder.')
    parser.add_argument('--test-file', default=DEFAULT_TEST_FILE, type=str, help='Test file to run.')
    parser.add_argument('--admin-token', default=DEFAULT_ADMIN_TOKEN, type=str, help='Admin token to access the API.')
    parser.add_argument('--alert-time', default=DEFAULT_CHART, type=int, help='Alert time in seconds. If a call takes more than this time, an alert will be shown.')
    parser.add_argument('--chart', default=DEFAULT_AVERAGE_TIME, type=bool, help='Show chart with results.')
    parser.add_argument('--chart-seconds', default=DEFAULT_CHART_SECONDS, type=int, help='Seconds to show in the chart.')
    parser.add_argument('--chart-top-endpoints', default=DEFAULT_CHART_TOP_ENDPOINTS, type=bool, help='Show top endpoints in the chart.')
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
    
    global admin_token_value
    global host_value
    
    admin_token_value = args.admin_token
    host_value = args.host + args.prefix
    
    chart_seconds = args.chart_seconds if args.chart_seconds > 0 else args.alert_time
        
    print("Starting benchmark...\n")
    benchmark(args.results, content_json, args.register_average_time, args.register_average_endpoint, args.register_average_method, args.register_call_time, args.alert_time, args.chart, chart_seconds)
    print("\nBenchmark finished.")

if __name__ == '__main__':
    main()