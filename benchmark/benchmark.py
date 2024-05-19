
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import matplotlib.pyplot as plt
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
DEFAULT_CHART_TOP_ENDPOINTS = 5
DEFAULT_CHART_TOP_ENDPOINTS_INDIVIDUAL = 8
DEFAULT_CHART = True
    
SEQUENCE = "sequence"
PARALLEL = "parallel"
ENDPOINT = "endpoint"
GENERAL_ENDPOINT = "general_endpoint"
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
   
PARAM_NAME = "{param}"
   
ADMIN_TOKEN = "ADMIN_TOKEN"
HOST = "HOST"

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]

AVERAGE_JSON_FILE_NAME = "average_results.json"
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
 
 


AVERAGE_COLUMNS = ['ENDPOINT', 'AVERAGE TIME', 'CORRECT STATUS', 'INCORRECT STATUS', 'TOTAL STATUS', 'TOTAL CALLS', 'METHOD', 'AVERAGE TIME', 'CORRECT STATUS', 'INCORRECT STATUS', 'TOTAL STATUS', 'TOTAL CALLS']

RESULTS_COLUMN = ['ENDPOINT', 'METHOD', 'TIME', 'STATUS', 'STATUS EXPECTED', 'OK']

AVERAGE_METHOD = 'average_method'
AVERGAE_TIME = 'average_time'
PERCENT_CORRECT_STATUS = 'percent_correct_status'
PERCENT_INCORRECT_STATUS = 'percent_incorrect_status'
TOTAL_CALLS = 'total_calls'
TOTAL_CHECKED_STATUS = 'total_checked_status'
TOTAL_CORRECT_STATUS = 'total_correct_status'
TOTAL_INCORRECT_STATUS = 'total_incorrect_status'

METHOD = 'method'
TIME = 'time'
STATUS_EXPECTED = 'status_expected'
STATUS = 'status'
OK = 'ok'

WRONG_OK_CLASS = 'wrong_ok'
ALERT_STATUS_CLASS = 'alert_status'

METHOD_COLUMN_CLASS = 'method_column'
AVERAGE_TABLE_CLASS = 'average_table'
RESULTS_TABLE_CLASS = 'results_table'

CSS_HTML_FILE = """
 <style>
        table, th, td {
            border-collapse: collapse;
            border-bottom: 1px solid #ddd;
            color: #000;
            font-style: normal;
            font-weight: normal;
            
        }

        th, td {
            border-right: 1px solid #ddd;
        }

        td{
            border-right-color: #999;
            padding: 5px;
        }

        th{
            border-left: 1px solid #ddd;
        }

        table {
            width: 100%;
            
        }

        table tr:nth-child(even) {
            background-color: #e0e0e0;
        }

        table tr:hover {
            background-color: #cddde7 !important;
        }

        table tr th:first-child {
            color: rgb(45, 116, 101);
            font-weight: bold;
            padding: 5px;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
        }

        table tr.columns th{
            background-color: #019879;
            color: #fff;
            text-align: center;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
            font-weight: bold;
            padding: 10px;
        }

        table tr.columns th:first-child{
            border-top-left-radius: 10px;
            border: none
        }
        table tr.columns th:last-child{
            border-top-right-radius: 10px;
            border: none
        }

        th[rowspan] {
            color: #000;
            font-style: normal;
            font-weight: normal;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
            text-align: center;
            padding: 5px;
            background-color: #fff;
        }

        table.results_table tr th[rowspan]:first-child {
            color: rgb(45, 116, 101);
            font-weight: bold;
            padding: 5px;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
        }

        table.results_table tr th[rowspan]{
            color: #000;
            font-style: normal;
            font-weight: normal;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
            text-align: center;
            padding: 5px;
            background-color: #fff;
            vertical-align: top;
        }

        table.results_table tr.columns th{
            background-color: #019879;
            color: #fff;
            text-align: center;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
            font-weight: bold;
            padding: 10px;
        }

        table tr.wrong_ok {
            background-color: #f7e599;
        }

        table tr.alert_status {
            background-color: #e97777;
        }

        h1 {
            color: #fff;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
            font-size: 2.5em;
            font-weight: bold;
            text-align: center;
            background-color: #019879;
        }

        h2 {
            color: #019879;
            font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
            font-size: 2em;
            font-weight: bold;
            text-align: center;
            cursor: pointer;
            user-select: none;
        }
        
        h2.hided {
            color: #46615c;
        }

        .warning_errors_container{
            display: flex;
            justify-content: center;
            flex-direction: column;
            align-items: center;
            font-size: 1.2em;
            font-family: 'Courier New', Courier, monospace;
            font-weight: bold;
        }

        .warning_errors_container .warnings{
            color: #e9be63;
        }

        .warning_errors_container .errors {
            color: #df4747;
        }
    </style>
"""

SCRIPT_HTML_FILE = """

    <script>
        btn_average = document.getElementById('title_average');
        btn_results = document.getElementById('title_results');
        btn_charts = document.getElementById('title_charts');

        container_average = document.getElementById('average_table_container');
        container_results = document.getElementById('results_table_container');
        container_charts = document.getElementById('charts_images');

        btn_average.addEventListener('click', e => {
            show = container_average.style.display == 'none' ? true : false;
            show ? container_average.style.display = 'block' : container_average.style.display = 'none';
            !show ? btn_average.classList.add('hided') : btn_average.classList.remove('hided');
            
        });

        btn_results.addEventListener('click', e => {
            show = container_results.style.display == 'none' ? true : false;
            show ? container_results.style.display = 'block' : container_results.style.display = 'none';
            !show ? btn_results.classList.add('hided') : btn_results.classList.remove('hided');
        });
        
        btn_charts.addEventListener('click', e => {
            show = container_charts.style.display == 'none' ? true : false;
            show ? container_charts.style.display = 'block' : container_charts.style.display = 'none';
            !show ? btn_charts.classList.add('hided') : btn_charts.classList.remove('hided');
        });
    </script>

"""

DECIMALS_ROUND = 2
 
def order_results(results: dict):
    
    for k, v in results.items():
        results[k] = sorted(v, key=lambda x: x[TIME], reverse=True)
        
    sorted_results = sorted(results.items(), key=lambda x: x[1][0][TIME], reverse=True)
    
    return dict(sorted_results)
    

def order_average_results(results: dict):
    
    for k, v in results.items():
        sorted_methods = sorted(v[AVERAGE_METHOD].items(), key=lambda x: x[1][AVERGAE_TIME], reverse=True)
        results[k][AVERAGE_METHOD] = dict(sorted_methods)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1][AVERGAE_TIME], reverse=True)
    
    return dict(sorted_results)
 
def generate_average_chart(average_results: dict, output_folder='results/', top_k=5):
        
        labels = list(average_results.keys())[:top_k]
        values = [round(average_results[k][AVERGAE_TIME], DECIMALS_ROUND) for k in labels]

        def make_autopct(values):
                total = sum(values)
                def my_autopct(pct):
                        # Calcula el valor correspondiente al porcentaje
                        actual_value = pct/100. * total
                        # Encuentra el valor en la lista más cercano al valor calculado
                        closest = min(values, key=lambda x: abs(x-actual_value))
                        return "{:.1f}%\n({:.2f})".format(pct, closest)
                return my_autopct

        fig, ax = plt.subplots()
        ax.pie(values, labels=['']*len(values), autopct=make_autopct(values), startangle=90)
        ax.axis('equal')
        ax.legend(labels, bbox_to_anchor=(1, 1), title='Endpoints', fontsize='small', title_fontsize='medium')
        plt.title(f'Media de tiempo de respuesta de los {top_k} primeros endpoints')
        
        plt.tight_layout()
        
        file_name1 = 'top_average_chart.png'
        fig.savefig(os.path.join(output_folder, file_name1), bbox_inches='tight')
        
        endpoint_name = list(average_results.keys())[0]
        average_method = average_results[endpoint_name][AVERAGE_METHOD]
        labels = list(average_method.keys())
        values = [round(average_method[k][AVERGAE_TIME], DECIMALS_ROUND) for k in labels]

        def make_autopct(values):
                total = sum(values)
                def my_autopct(pct):
                        # Calcula el valor correspondiente al porcentaje
                        actual_value = pct/100. * total
                        # Encuentra el valor en la lista más cercano al valor calculado
                        closest = min(values, key=lambda x: abs(x-actual_value))
                        return "{:.1f}%\n({:.2f})".format(pct, closest)
                return my_autopct

        fig, ax = plt.subplots()
        ax.pie(values, labels=['']*len(values), autopct=make_autopct(values), startangle=90)
        ax.axis('equal')
        ax.legend(labels, bbox_to_anchor=(1, 1), title='Endpoints', fontsize='small', title_fontsize='medium')
        plt.title(f'Media de tiempo de respuesta de \'{endpoint_name}\'')
        
        plt.tight_layout()
        
        file_name2 = 'endpoint_average_chart.png'
        fig.savefig(os.path.join(output_folder, file_name2), bbox_inches='tight')
        
        return file_name1, file_name2
        
def generate_results_chart(results: dict, output_folder='results/', top_k=8):
        
        call_list = []

        for k, v in results.items():
                for n in v:
                        call_list.append(
                        {
                                'endoint': n[METHOD] + ' ' + k,
                                'time': n[TIME],
                        }
                        )
                
        call_list = sorted(call_list, key=lambda x: x['time'], reverse=True)

        top_k = 8

        labels = [f"{idx}. {x['endoint']}" for idx, x in enumerate(call_list[:top_k], 1)]
        values = [round(x['time'], DECIMALS_ROUND) for x in call_list[:top_k]]

        print(labels)
        print(values)

        fig, ax = plt.subplots()
        bars = ax.bar(labels, values, color='skyblue')

        for bar in bars:
                yval = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), va='bottom', ha='center', color='black')

        plt.xticks(rotation=45, ha='right')
        ax.plot(labels, values, color='red', marker='o', linestyle='dashed', linewidth=1, markersize=2)
        ax.set_ylabel('Tiempo (s)')
        ax.set_xlabel('Endpoints')
        ax.set_title(f'Tiempo de respuesta de los {top_k} endpoints más lentos')
        
        file_name = 'top_results_chart.png'
        
        path = os.path.join(output_folder, file_name)
        
        plt.tight_layout()
        
        fig.savefig(path, bbox_inches='tight')
        
        return file_name
    
def generate_average_table(results:dict):
    columns = "<tr class=\"columns\">" + "".join([f"<th>{col}</th>" for col in AVERAGE_COLUMNS]) + "</tr>"
    
    content = ""
        
    for endpoint_name, endpoint in results.items():
                
        rowspans = len(endpoint[AVERAGE_METHOD])
        average_time = round(endpoint[AVERGAE_TIME], DECIMALS_ROUND)
        percent_correct_status = round(endpoint[PERCENT_CORRECT_STATUS], DECIMALS_ROUND)
        percent_incorrect_status = round(endpoint[PERCENT_INCORRECT_STATUS], DECIMALS_ROUND)
        total_calls = endpoint[TOTAL_CALLS]
        total_checked_status = endpoint[TOTAL_CHECKED_STATUS]
        total_correct_status = endpoint[TOTAL_CORRECT_STATUS]
        total_incorrect_status = endpoint[TOTAL_INCORRECT_STATUS]
        
        average_method:dict = endpoint[AVERAGE_METHOD]
        
        method_name = list(average_method.keys())[0]
        method = average_method[method_name]
        
        
        row = f"""
            <tr>
                <th rowspan="{rowspans}">{endpoint_name}</th>
                <th rowspan="{rowspans}">{average_time}s</th>
                <th rowspan="{rowspans}">{total_correct_status} ({percent_correct_status}%)</th>
                <th rowspan="{rowspans}">{total_incorrect_status} ({percent_incorrect_status}%)</th>
                <th rowspan="{rowspans}">{total_checked_status}</th>
                <th rowspan="{rowspans}">{total_calls}</th>
                
                
                <td class="{METHOD_COLUMN_CLASS}">{method_name}</td>
                <td class="{METHOD_COLUMN_CLASS}">{round(method[AVERGAE_TIME], DECIMALS_ROUND)}s</td>
                <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_CORRECT_STATUS]} ({round(method[PERCENT_CORRECT_STATUS], DECIMALS_ROUND)}%)</td>
                <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_INCORRECT_STATUS]} ({round(method[PERCENT_INCORRECT_STATUS], DECIMALS_ROUND)}%)</td>
                <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_CHECKED_STATUS]}</td>
                <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_CALLS]}</td>
            </tr>
        """
        
        if rowspans > 1:
        
            method_names = list(average_method.keys())[1:]
            
            for method_name in method_names:
                method = average_method[method_name]
                row += f"""
                    <tr>
                        <td class="{METHOD_COLUMN_CLASS}">{method_name}</td>
                        <td class="{METHOD_COLUMN_CLASS}">{round(method[AVERGAE_TIME], DECIMALS_ROUND)}s</td>
                        <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_CORRECT_STATUS]} ({round(method[PERCENT_CORRECT_STATUS], DECIMALS_ROUND)}%)</td>
                        <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_INCORRECT_STATUS]} ({round(method[PERCENT_INCORRECT_STATUS], DECIMALS_ROUND)}%)</td>
                        <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_CHECKED_STATUS]}</td>
                        <td class="{METHOD_COLUMN_CLASS}">{method[TOTAL_CALLS]}</td>
                    </tr>
                """
                
        content += row
        
    return f"""
        <table class="{AVERAGE_TABLE_CLASS}">
            {columns}
            {content}
        </table>
    """
        

def generate_results_table(results: dict):
    columns = "<tr class=\"columns\">" + "".join([f"<th>{col}</th>" for col in RESULTS_COLUMN]) + "</tr>"
    
    content = ""
        
    warnings = 0
    errors = 0
        
    for endpoint_name, endpoint in results.items():
            
        endpoint = results[endpoint_name]
        
        rowspans = len(endpoint)
        
        for i, result in enumerate(endpoint):
            row = ""
            
            classes = []
            
            if not bool(result[OK]):
                warnings += 1
                classes.append(WRONG_OK_CLASS)
                
            if int(result[STATUS]) >= 500:
                errors += 1
                classes.append(ALERT_STATUS_CLASS)
            
            classes = " ".join(classes)
            
            if i == 0:
                
                row = f"""
                    <tr class="{classes}">
                        <th rowspan="{rowspans}">{endpoint_name}</th>
                        <td>{result[METHOD]}</td>
                        <td>{round(result[TIME], DECIMALS_ROUND)}s</td>
                        <td>{result[STATUS]}</td>
                        <td>{result[STATUS_EXPECTED]}</td>
                        <td>{'✅' if bool(result[OK]) else '❌'}</td>
                    </tr>
                """
            else:
                row = f"""
                    <tr class="{classes}">
                        <td>{result[METHOD]}</td>
                        <td>{round(result[TIME], DECIMALS_ROUND)}s</td>
                        <td>{result[STATUS]}</td>
                        <td>{result[STATUS_EXPECTED]}</td>
                        <td>{'✅' if bool(result[OK]) else '❌'}</td>
                    </tr>
                """
                
            content += row
        
    return f"""
        <table class="{RESULTS_TABLE_CLASS}">
            {columns}
            {content}
        </table>
        <div class=\"warning_errors_container\">
            <p class="warnings">Warnings: <span>{warnings}</span></p>
            <p class="errors">Errors: <span>{errors}</span></p>
        </div>
    """

def save_as_html(average_results, all_results, output_folder='results/', top_endpoints=5, top_endpoints_individual=8):
    
    average_results = order_average_results(average_results)
    all_results = order_results(all_results)
    
    average_table = generate_average_table(average_results)
    results_table = generate_results_table(all_results)

    folder_img = os.path.join(output_folder, 'img')
    if not os.path.exists(folder_img):
        os.makedirs(folder_img)

    img1, img2 = generate_average_chart(average_results, output_folder=folder_img, top_k=top_endpoints)
    img3 = generate_results_chart(all_results, output_folder=folder_img, top_k=top_endpoints_individual)
    
    img1 = os.path.join('img', img1)
    img2 = os.path.join('img', img2)
    img3 = os.path.join('img', img3)
    
    html_text = f"""<!DOCTYPE html>
        
        <html>
        <head>
            <title>Resultados</title>
            {CSS_HTML_FILE}
        </head>
        <body>
            <h1>Resultados</h1>
            
            <h2 id=\"title_average\">Resultados médios</h2>
            <div id=\"average_table_container\">
                {average_table}
            </div>
            
            <h2 class=\"hided\" id=\"title_results\">Resultados individuales</h2>
            <div id=\"results_table_container\" style=\"display: none\">
                {results_table}
            </div>
            
            <h2 id=\"title_charts\">Gráficos</h2>
            
            <div id=\"charts_images\">
                <img class=\"img-chart\" src=\"{img1}\" alt=\"Top average chart\">
                <img class=\"img-chart\" src=\"{img2}\" alt=\"Endpoint average chart\">
                <img class=\"img-chart\" src=\"{img3}\" alt=\"Top results chart\">
            </div>
            
            {SCRIPT_HTML_FILE} 
            
        </body>
        </html>"""
        
    file_name = 'results.html'
    
    output_file = os.path.join(output_folder, file_name)
        
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(html_text)
 
def save_results_json(results_path, results):
    with open(results_path, 'w') as file:
        json.dump(results, file, indent=4)
 
def process_results(results_path, top_endpoints=5, top_endpoints_individual=8):
    
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
                "total_calls": results_method[result["method"]]["total_calls"] + 1 if result["method"] in results_method else 1,
                "total_checked_status": results_method[result["method"]]["total_checked_status"] if result["method"] in results_method else 0,
                "total_correct_status": results_method[result["method"]]["total_correct_status"] if result["method"] in results_method else 0,
                "total_incorrect_status": results_method[result["method"]]["total_incorrect_status"] if result["method"] in results_method else 0
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
        
    file_name_average = AVERAGE_JSON_FILE_NAME
    
    results_path_average = os.path.join(results_path, file_name_average)
        
    save_results_json(results_path_average, average_results)
    
    file_name_results = JSON_FILE_NAME
    
    results_path_results = os.path.join(results_path, file_name_results)
    
    save_results_json(results_path_results, benchmark_results)
    
    save_as_html(average_results, benchmark_results, results_path, top_endpoints, top_endpoints_individual)
 
def register_benchmark(endpoint, method, time, status, status_expected):
    
    if endpoint not in benchmark_results:
        benchmark_results[endpoint] = []
    
    benchmark_results[endpoint].append({"method": method, "time": time, "status": status, "status_expected": status_expected if status_expected else "-", "ok": (status == status_expected) if status_expected else True})
    
def make_request(method, endpoint, body, headers, retries=10):
    
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
            print(f"Retrying... {i + 1} of {retries}.")

    return (response.json() if response.status_code != 204 else {}), response.status_code, duration
    
def make_test_call(test, stop_on_error=False):
    
    response, status, duration = make_request(test[METHOD], test[HOST] + test[ENDPOINT], test[BODY], test[HEADERS])
    
    if test[RESPONSE] is not None:
        variables[test[RESPONSE]] = response
        
    register_benchmark(test[GENERAL_ENDPOINT], test[METHOD], duration, status, test[EXPECTED_STATUS])    
    
    print(f"\n{test[TITLE]}\n{test[METHOD]} {test[ENDPOINT]} - {status} ... {duration} seconds. Expected: {test[EXPECTED_STATUS] if test[EXPECTED_STATUS] else '-'}\nBODY:\n\t{test[BODY]}\nHEADERS:\n\t{test[HEADERS]}\nRESPONSE:\n\t{response}")
    
    if stop_on_error and (test[EXPECTED_STATUS] is not None and status != test[EXPECTED_STATUS] or status >= 500):
    
        print(f"Error in test {test[TITLE]}")
        exit(1)
    
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
    
def compile_string(string: str|dict|list, value_parser=None):
    
    if isinstance(string, dict):
        return {key: compile_string(string[key], value_parser=value_parser) for key in string}
    
    if isinstance(string, list):
        return [compile_string(value, value_parser=value_parser) for value in string]
    
    if not isinstance(string, str):
        return string
    
    def process_function(var):
        function = var[len(FUNCTION_PREFIX):]
        function_name = function.split('(')[0]
        function_args = function.split('(')[1].split(')')[0].split(',')
        function_args = [compile_string(arg, value_parser=value_parser) for arg in function_args] 
    
        if function_name not in functions:
            raise Exception(f"Function {function_name} not found.")
        
        return functions[function_name](*function_args)
        
    string_result = string.replace(f"{{{ADMIN_TOKEN}}}", admin_token_value)
    
    var_names = extract_braced_content(string_result)
    
    for var in var_names:
                
        if value_parser is not None:
            value = value_parser
        elif var.startswith(FUNCTION_PREFIX):
            value = process_function(var)
        else:
            vars = var.split('.')
            
            if vars[0] not in variables:
                raise Exception(f"Variable {vars[0]} not found in responses.")
            
            response = variables[vars[0]]
            
            value = get_value(response, vars[1:]) if len(vars) > 1 else response
        
        string_result = string_result.replace(f"{{{var}}}", value)
    
    return string_result
    
def get_data_call(test):
        
    test[GENERAL_ENDPOINT] = compile_string(test[ENDPOINT], value_parser=PARAM_NAME)
    test[ENDPOINT] = compile_string(test[ENDPOINT])
    
    if HOST not in test: test[HOST] = host_value
    if METHOD not in test: test[METHOD] = "GET"
    if TITLE not in test: test[TITLE] = ""
    if BODY not in test: test[BODY] = {}
    if HEADERS not in test: test[HEADERS] = DEFAULT_HEADERS
    if RESPONSE not in test: test[RESPONSE] = None
    if EXPECTED_STATUS not in test: test[EXPECTED_STATUS] = None
    
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
    
def sequence(tests: list, stop_on_error: bool = False):
    for t in tests:
        test(t, stop_on_error)

def parallel(tests: dict, stop_on_error: bool = False):
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(test, t, stop_on_error) for t in tests]
        
    for future in futures:
        future.result()
    
def test(test_conf: dict, stop_on_error: bool = False):
    
    if ENABLED in test_conf and not test_conf[ENABLED]: return
    
    n = test_conf[N] if N in test_conf else 1
    
    for _ in range(n):
        
        if VARS in test_conf: set_vars(test_conf[VARS])
        if START in test_conf: test(test_conf[START], stop_on_error)
        if SEQUENCE in test_conf: sequence(test_conf[SEQUENCE], stop_on_error)
        if PARALLEL in test_conf: parallel(test_conf[PARALLEL], stop_on_error)
        if ENDPOINT in test_conf:
            test_conf = get_data_call(test_conf)
            make_test_call(test_conf, stop_on_error)
        if END in test_conf: test(test_conf[END], stop_on_error)
    
def benchmark(results_path: str, tests: dict, stop_on_error: bool = False, top_endpoints: int = 5, top_endpoints_individual: int = 8):
    
    test(tests, stop_on_error)
    
    print("\nProcessing results...")
    
    process_results(results_path, top_endpoints, top_endpoints_individual)

def main():
    
    parser = argparse.ArgumentParser(description='Test of performance to booking API.')

    parser.add_argument('--host', default=DEFAULT_HOST, type=str, help='Host to connect.')
    parser.add_argument('--prefix', default=DEFAULT_PREFIX, type=str, help='API endpoint prefix.')
    parser.add_argument('--results', default=DEFAULT_RESULTS, type=str, help='Results folder.')
    parser.add_argument('--test-file', default=DEFAULT_TEST_FILE, type=str, help='Test file to run.')
    parser.add_argument('--admin-token', default=DEFAULT_ADMIN_TOKEN, type=str, help='Admin token to access the API.')
    parser.add_argument('--stop-on-error', action='store_true', default=False, help='Stop the test when an error occurs.')
    parser.add_argument('--top-endpoints', default=DEFAULT_CHART_TOP_ENDPOINTS, type=int, help='Number of top endpoints to show in the chart.')
    parser.add_argument('--top-endpoints-individual', default=DEFAULT_CHART_TOP_ENDPOINTS_INDIVIDUAL, type=int, help='Number of top endpoints to show in the individual chart.')

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
            
    print("Starting benchmark...\n")
    benchmark(args.results, content_json, args.stop_on_error, args.top_endpoints, args.top_endpoints_individual)
    print("\nBenchmark finished.")

if __name__ == '__main__':
    main()