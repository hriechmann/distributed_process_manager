from importlib._bootstrap import _check_name
from tkinter.scrolledtext import example

__author__ = 'hriechma'

# import rpyc
# import time
# import sys
# from eu.hriechmann.distributed_process_manager.server import ManagerCommands
#
# process_descriptions = []
#
# class ManagerService(rpyc.Service):
#
#     def exposed_process_status_changed(self, process_id):
#         print("Reached manager")
#         #for process in process_descriptions:
#         #    if process.id == process_id:
#         #        print("New status of process", process.id, "is: ",process.status)
#         #        break
#
# class Manager:
#     def __init__(self, server, port, process_definitions_file):
#         self.server = server
#         self.port = port
#         self.process_definitions_file = process_definitions_file
#         self.conn = None
#         self.process_definitions = []
#
#     def start(self):
#         #TODO read process definitions from file
#         #connect to server
#         while True:
#             try:
#                 self.conn = rpyc.connect("localhost", 18861, service=ManagerService)
#                 break
#             except:
#                 print("Could not connect")
#                 time.sleep(10)
#         self.conn.root.register_manager()
#         test = self.conn.root.create_process_definition("otho", "DataAq", """UBiCIApplication""", "/media/local/hriechma/redmine-git/ubici_application/")
#         process_descriptions.append(test)
#
#     def update_status(self):
#         for process_description in process_descriptions:
#                 print("Process id: ", process_description.id, "has status: ", process_description.status)
#
#     def issue_command(self, command, process_id):
#         for process in process_descriptions:
#             if process.id == process_id:
#                 self.conn.root.new_manager_command(process, command)
#
#     def run(self):
#         while True:
#             time.sleep(1)
#             self.update_status()
#
#     def get_process_descriptions(self):
#         return process_descriptions
#
# import time
# import rpyc
# class SimpleManagerService(rpyc.SlaveService):
#
#     def on_connect(self):
#         pass
#
#     def on_disconnect(self):
#         pass
#
#     def exposed_get_my_jobs(self, hostname):
#         return ["Test", ]
#
#
# class SimpleManager:
#
#     def __init__(self):
#         self.conn = None
#
#     def start(self):
#         self.conn = rpyc.connect("localhost", 18861, service=SimpleManagerService)
#         self.conn.root.register_manager()
#
#     def run(self):
#         while True:
#             time.sleep(1)
#
#
# #
# # if __name__ == "__main__":
# #     #myManager = Manager("localhost", 18861, "todo")
# #     myManager = SimpleManager()
# #     myManager.start()
# #     myManager.run()
#
# if __name__ == "__main__":
#     from rpyc.utils.server import ThreadedServer
#     t = ThreadedServer(SimpleManagerService, port=44445)
#     t.start()


import zmq
import pickle
import threading
import queue
import copy
import configparser
from eu.hriechmann.distributed_process_manager.common import Message, ManagerCommands, \
    ServerCommands, ProcessDescription, ProcessStatus, ClientCommands, ClientStati, ClientDescription
import xml.etree.ElementTree as ET


class Manager(threading.Thread):

    def __init__(self, id, config_file, server, port):
        super(Manager, self).__init__()
        self.id = id
        self.context = zmq.Context()
        self.server = server
        self.port = port
        self.socket = None
        self.known_clients = []
        self.process_descriptions = []
        # config = configparser.ConfigParser()
        # try:
        #     config.read(config_file)
        # except IOError as e:
        #     print("Could not read configfile: ", config_file)
        #     raise e
        # for section in config.sections():
        #     id = config[section]["id"]
        #     target_host = config[section]["target_host"]
        #     command = config[section]["command"]
        #     if "working_directory" in config[section]:
        #         working_directory = config[section]["working_directory"]
        #     if "env" in config[section]:
        #
        #

        #test_process = ProcessDescription("DataAq", 'otho', """UBiCIApplication""",
                                          # "/media/local/hriechma/redmine-git/ubici_application/",
                                          # dict(LD_LIBRARY_PATH="/media/local/hriechma/redmine-git/libubici/",
                                          #      DISPLAY=":0", HOME="/homes/hriechma"))
        tree = ET.parse(config_file)
        root = tree.getroot()
        for xml_desc in root.getchildren():
            if xml_desc.tag == 'process':
                extracted_attributes = {}
                for attribute in xml_desc.getchildren():
                    if attribute.tag in ["id", "target_host", "command", "working_directory"]:
                        extracted_attributes[attribute.tag] = attribute.text
                    elif attribute.tag in ["env", ]:
                        extracted_attributes[attribute.tag] = {}
                        for key in attribute.getchildren():
                            extracted_attributes[attribute.tag][key.tag] = key.text
                    else:
                        raise Exception("Unknown attribute of process: ", attribute.tag)
                if not "id" in extracted_attributes:
                    raise Exception("Process missing id")
                if not "target_host" in extracted_attributes:
                    raise Exception("Process with id: "+str(extracted_attributes["id"]+" has no target_host"))
                if not "command" in extracted_attributes:
                    raise Exception("Process with id: "+str(extracted_attributes["id"]+" has no command"))
                new_process = ProcessDescription(extracted_attributes["id"],
                                                 extracted_attributes["target_host"],
                                                 extracted_attributes["command"],
                                                 extracted_attributes["working_directory"]
                                                 if "working_directory" in extracted_attributes else "",
                                                 extracted_attributes["env"]
                                                 if "env" in extracted_attributes else {})
                self.process_descriptions.append(new_process)
            elif xml_desc.tag == 'client':
                extracted_attributes = {}
                for attribute in xml_desc.getchildren():
                    if attribute.tag in ["hostname", "local_path"]:
                        extracted_attributes[attribute.tag] = attribute.text
                    else:
                        raise Exception("Unknown attribute of client: ", attribute.tag)
                if not "hostname" in extracted_attributes:
                    raise Exception("Client missing hostname")
                if not "local_path" in extracted_attributes:
                    extracted_attributes["local_path"] = ""
                print("Local path: ", extracted_attributes["local_path"])
                self.known_clients.append(ClientDescription(extracted_attributes["hostname"].encode("ascii"),
                                                            extracted_attributes["local_path"]))
            else:
                raise Exception("Bad xml, exspected tag: process or client")
        self.process_status = []
        self.internal_message_queue = queue.Queue()

    def run(self):
        # Socket to talk to server
        print("Connecting to server…"+self.server+" on port: "+str(self.port))
        self.socket = self.context.socket(zmq.DEALER)
        identity = str(self.id)
        self.socket.identity = identity.encode('ascii')
        self.socket.connect("tcp://"+self.server+":"+str(self.port))

        # Register with server
        message = Message("", ManagerCommands.REGISTER)
        print("Sending request %s …" % message)
        self.socket.send(pickle.dumps(message))

        while True:
            #Wait for commands
            poll = zmq.Poller()
            poll.register(self.socket, zmq.POLLIN)
            sockets = {}
            while not self.socket in sockets:
                sockets = dict(poll.poll(1000))
                while not self.internal_message_queue.empty():
                    new_message = self.internal_message_queue.get()
                    if new_message == "TERMINATE_MANAGER":
                        return
                    self.socket.send(pickle.dumps(new_message))
            message = pickle.loads(self.socket.recv())
            if message.command != ServerCommands.SEND_KEEPALIVE:
                print("Received request: %s" % message)
            new_messages = self.process_msg(message)
            for new_message in new_messages:
                self.socket.send(pickle.dumps(new_message))

    def process_msg(self, message):
        if message.command == ServerCommands.SEND_KEEPALIVE:
            return [Message("", ManagerCommands.KEEPALIVE), ]
        elif message.command == ServerCommands.NEW_CLIENT:
            new_client = message.payload
            for client in self.known_clients:
                if client.hostname == new_client:
                    client.status = ClientStati.RUNNING
            print("Known clients are: ", self.known_clients)
            ret = []
            for process_desc in self.process_descriptions:
                if process_desc.target_host.encode('ascii') == new_client:
                    print("Found client for process", process_desc)
                    self.process_status.append(ProcessStatus(new_client, process_desc))
                    ret.append(Message(new_client, ManagerCommands.INIT_PROCESS, process_desc))
            return ret
        elif message.command == ServerCommands.LOST_CLIENT:
            lost_client = message.payload
            for client in self.known_clients:
                if client.hostname == lost_client:
                    client.status = ClientStati.NOT_RUNNING

        elif message.command == ClientCommands.PROCESSSTATUS_CHANGED:
            for process in self.process_status:
                if process.process_desc.id == message.payload[0]:
                    process.status = message.payload[1]
        elif message.command == ClientCommands.PROCESS_LOGS:
            for process in self.process_status:
                if process.process_desc.id == message.payload[0]:
                    process.log_out += message.payload[1]
                    process.log_err += message.payload[2]
        return []

    def issue_command(self, command, process_id):
        print("I should send message", command, "to ", process_id)
        if command == "TERMINATE_MANAGER":
            self.internal_message_queue.put(command)
        for process in self.process_status:
            if process.process_desc.id == process_id:
                print("Found matching process")
                self.internal_message_queue.put(Message(process.responsible_client, command, process_id))

    def get_process_descriptions(self):
        return copy.deepcopy(self.process_descriptions)

    def get_process_stati(self):
        return self.process_status

    def get_client_stati(self):
        return self.known_clients

if __name__ == "__main__":
    myManager = Manager("otho-manager", "otho", 5556)
    myManager.start()
    myManager.join()




