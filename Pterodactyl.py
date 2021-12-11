from __future__ import annotations
from typing import List
import socket
import requests
import websocket
import json
import threading

class Account:
    def __init__(self, api_key, base_url):
        self._API_KEY = api_key
        self._base_url = base_url
        self._base_headers = {
            "Authorization": "Bearer "+self._API_KEY,
            "Accept": "application/data_json",
            "Content-Type": "application/data_json"
        }
        self._load_account_detail()
    def _load_account_detail(self):
        route = self._base_url + "/api/client/account"
        response = requests.request('GET', route, headers=self._base_headers)
        data_json = response.json()["attributes"]
        self.id = data_json["id"]
        self.is_admin = data_json["admin"]
        self.username = data_json["username"]
        self.email = data_json["email"]
        self.first_name = data_json["first_name"]
        self.last_name = data_json["last_name"]
        self.language = data_json["language"]

    def get_servers(self) -> List[Server]:
        """
        Get all the server of the account
        Returns: List of servers
        """
        route = self._base_url + "/api/client"
        response = requests.request('GET', route, headers=self._base_headers)
        self.servers = []
        for server in response.json()["data"]:
            self.servers.append(self.Server(server,self._base_url, self._base_headers))
        return self.servers

    class Server:
        def __init__(self,data_json,base_url, base_headers):
            self.attributes = self.Attributes(data_json["attributes"])
            self._base_url = base_url
            self._base_headers = base_headers
            self.resources = None
            self.ws = None
            self.logs = []
        def _open_websocket(self):
            res = requests.get(self._base_url + "/api/client/servers/" + self.attributes.identifier + "/websocket", headers=self._base_headers).json()["data"]
            token = res["token"]
            url = res["socket"]
            self.ws = websocket.WebSocket()
            self.ws.connect(url)
            self.ws.send('{"event":"auth", "args":["'+token+'"]}')
        def _websocket_listener(self):
            if self.ws == None:
                self._open_websocket()
            self.ws.send('{"event":"send logs", "args":[null]}')
            while self.ws_thread_running:
                data = json.loads(self.ws.recv())
                if data["event"] == "console output":
                    self.logs.append(data["args"][0])
                elif data["event"] == "server stats":
                    self.resources.cpu_absolute = data["args"]["cpu_absolute"]
                    self.resources.memory_bytes = data["args"]["memory_bytes"]
                    self.resources.disk_bytes = data["args"]["disk_bytes"]
                    self.attributes.limits.max_memory = data["args"]["memory_limit_bytes"]
                    self.resources.network_rx_bytes = data["args"]["network"]["rx_bytes"]
                    self.resources.network_tx_bytes = data["args"]["network"]["tx_bytes"]
                    self.current_state = data["args"]["state"]
                elif data["event"] == "status":
                    self.current_state = data["args"][0]
                elif data["event"] == "token expired":
                    self.ws = None
                    self._open_websocket()
        def _send_power_action(self, action):
            if self.ws == None:
                route = self._base_url + "/api/client/servers/" + self.attributes.identifier +"/power"
                return requests.request('POST', route, data='{"signal":"'+action+'"}', headers=self._base_headers).status_code
            else:
                self.ws.send('{"event":"set state","args":["'+action+'"]}')
                return 204

        def get_usage(self):
            """
            Gets the usage of the server and therefor update server.resources.* and server.current_state
            Returns: self
            """
            route = self._base_url + "/api/client/servers/" + self.attributes.identifier + "/resources"
            data_json = requests.request('GET', route, headers=self._base_headers).json()["attributes"]
            self.current_state = data_json["current_state"]
            self.is_suspended = data_json["is_suspended"]
            self.resources = self.Resources(data_json["resources"])
            return self
        def start(self) -> bool:
            """
            Start the server
            Uses websocket if available
            Return: successfull
            """
            status_code = self._send_power_action("start")
            if status_code == 204:
                return True
            else: return False
        def restart(self) -> bool:
            """
            Restarts the server
            Uses websocket if available
            Returns: success
            """
            status_code = self._send_power_action("restart")
            if status_code == 204:
                return True
            else: return False
        def stop(self) -> bool:
            """
            Stoppes the server
            Uses websocket if available
            Returns: success
            """
            status_code = self._send_power_action("stop")
            if status_code == 204:
                return True
            else: return False
        def kill(self) -> bool:
            """
            Kills the server
            Uses websocket if available
            Returns: success
            """
            status_code = self._send_power_action("kill")
            if status_code == 204:
                return True
            else: return False
        def run_cmd(self,cmd) -> bool:
            """
            Runs a command on the server
            Uses the websocket if started
            Returns: (success, status_code)
            """
            if self.ws == None:
                route = self._base_url + "/api/client/servers/" + self.attributes.identifier +"/command"
                payload = '{"command":"'+cmd+'"}'
                status_code = requests.request('POST', route, headers=self._base_headers, data=payload).status_code
            else:
                self.ws.send('{"event":"send command","args":["'+cmd+'"]}')
                status_code = 204
            if status_code == 204:
                return (True, status_code)
            else: return (False, status_code)
        #TODO untested
        def get_backups(self) -> List[Backup]:
            """
            Gets the backups from the server
            UNTESTED
            """
            route = self._base_url + "/api/client/servers/" + self.attributes.identifier +"/backups"
            data_json = requests.request('GET', route, headers=self._base_headers).json()
            self.backups = []
            for backup in data_json["data"]:
                self.backups.append(self.Backup(backup)["attributes"])
            return self.backups
        #TODO untested
        def create_backup(self) -> Backup|int:
            """
            THIS IS UNTESTED
            Create a backup on the server.
            Returns:
                Backup if successfull
                status code if failed
            """
            route = self._base_url + "/api/client/servers/" + self.attributes.identifier +"/backups"
            res = requests.request('POST', route, headers=self._base_headers)
            if res.status_code == 200:
                return self.Backup(res.json()["backup"])
            else: return res.status_code
        def start_websocket_thread(self):
            """
            Start the websocket thread, which:
            - Gets the logs and updates server.logs
            - Gets the status and updates server.resources.* and server.current_state
            - Increases the speed of server power state changes and running server commands
            """
            self.ws_thread_running = True
            self._websocket_listener_thread = threading.Thread(target=self._websocket_listener, name="websocket_thread"+str(len(threading.enumerate())))
            self._websocket_listener_thread.start()
        def close_ws_socket(self):
            """
            Closes the websocket thread and websocket 
            """
            self.ws_thread_running = False

        class Attributes:
            def __init__(self, data_json):
                self.is_server_owner = data_json["server_owner"]
                self.identifier = data_json["identifier"]
                self.internal_id = data_json["internal_id"]
                self.uuid = data_json["uuid"]
                self.name = data_json["name"]
                self.node = data_json["node"]
                self.sftp_details = self.SFTP_Details(data_json["sftp_details"])
                self.description = data_json["description"]
                self.limits = self.Limits(data_json["limits"])
                self.invocation = data_json["invocation"]
                self.docker_image = data_json["docker_image"]
                self.egg_features = data_json["egg_features"]
                self.feature_limits = self.FeatureLimits(data_json["feature_limits"])
                self.status = data_json["status"]
                self.is_suspended = data_json["is_suspended"]
                self.is_installing = data_json["is_installing"]
                self.is_transferring = data_json["is_transferring"]
                self.relationships = self.Relationships(data_json["relationships"])
            class SFTP_Details:
                def __init__(self, data_json):
                    self.ip = data_json["ip"]
                    self.port = data_json["port"]
            class Limits:
                def __init__(self, data_json):
                    self.max_memory = data_json["memory"]
                    self.max_swap = data_json["swap"]
                    self.max_disk = data_json["disk"]
                    self.max_io = data_json["io"]
                    self.max_cpu = data_json["cpu"]
                    self.max_threads = data_json["threads"]
                    self.oom_disabled = data_json["oom_disabled"]
            class FeatureLimits:
                def __init__(self, data_json):
                    self.max_databases = data_json["databases"]
                    self.max_allocations = data_json["allocations"]
                    self.max_backups = data_json["backups"]
            class Relationships:
                def __init__(self,data_json):
                    self.allocations = []
                    for alloc in data_json["allocations"]["data"]:
                        self.allocations.append(self.Allocation(alloc["attributes"]))
                    self.variables = []
                    for var in data_json["variables"]["data"]:
                        self.variables.append(self.Variable(var["attributes"]))
                class Allocation:
                    def __init__(self,data_json):
                        self.id = data_json["id"]
                        self.ip = data_json["ip"]
                        self.ip_alias = data_json["ip_alias"]
                        self.port = data_json["port"]
                        self.notes = data_json["notes"]
                        self.is_default = data_json["is_default"]
                class Variable:
                    def __init__(self, data_json):
                        self.name = data_json["name"]
                        self.description = data_json["description"]
                        self.env_variable = data_json["env_variable"]
                        self.default_value = data_json["default_value"]
                        self.server_value = data_json["server_value"]
                        self.is_editable = data_json["is_editable"]
                        self.rules = data_json["rules"]
        class Resources:
            def __init__(self,data_json):
                self.memory_bytes = data_json["memory_bytes"]
                self.cpu_absolute = data_json["cpu_absolute"]
                self.disk_bytes = data_json["disk_bytes"]
                self.network_rx_bytes = data_json["network_rx_bytes"]
                self.network_tx_bytes = data_json["network_tx_bytes"]
        class Backup:
            def __init__(self,data_json):
                self.uuid = data_json["uuid"]
                self.name = data_json["name"]
                self.ignored_files = data_json["ignored_files"]
                self.sha256_hash = data_json["sha256_hash"]
                self.bytes = data_json["bytes"]
                self.created_at = data_json["created_at"]
                self.completed_at = data_json["completed_at"]