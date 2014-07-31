__author__ = 'hriechma'

# import rpyc
# from enum import Enum
#
# ManagerCommands = Enum("ManagerCommands", "NONE START STOP")
#
#
#
# class ProcessDefinitionsServer(rpyc.Service):
#
#     exposed_ProcessStatus = Enum("ProcessStatus", "WAITING_FOR_CLIENT CLAIMED DIED")
#
#
#     class exposed_ProcessDefinition:
#         def __init__(self, host, id, command, working_directory=""):
#             self.id = id
#             self.status = ProcessDefinitionsServer.exposed_ProcessStatus.WAITING_FOR_CLIENT
#             self.host = host
#             self.process_command = command
#             self.working_directory = working_directory
#             self.client_conn = None
#             self.manager_commands = ManagerCommands.NONE
#
#     process_definitions = []
#     manager_conn = None
#
#     def on_connect(self):
#         pass
#
#     def on_disconnect(self):
#         pass
#
#     def exposed_register_manager(self):
#         #ProcessDefinitionsServer.manager_conn = self._conn
#         pass
#
#     def exposed_create_process_definition(self, host, id, command, working_directory=""):
#         proc_def = ProcessDefinitionsServer.exposed_ProcessDefinition(host, id, command, working_directory)
#         ProcessDefinitionsServer.process_definitions.append(proc_def)
#         return proc_def
#
#     def exposed_register_processes(self, process_definitions):
#         ProcessDefinitionsServer.process_definitions.append(process_definitions)
#
#     def exposed_get_processes_for_host(self, hostname):
#         process_list=[]
#         for process in ProcessDefinitionsServer.process_definitions:
#             print(process.host+" "+hostname)
#             if process.host == hostname:
#                 process_list.append(process)
#         return process_list
#
#     def exposed_claim_process(self, process_definition):
#         process_definition.status = ProcessDefinitionsServer.exposed_ProcessStatus.CLAIMED
#         process_definition.client_conn = self._conn
#
#     def exposed_process_died(self, process_definition):
#         process_definition.status = ProcessDefinitionsServer.exposed_ProcessStatus.DIED
#
#     def exposed_new_manager_command(self, process, command):
#         print(process.id, command)
#         process.manager_commands = command

# import rpyc
# class SimpleDispatcherService(rpyc.Service):
#
#     exposed_manager_root = None
#
#     def on_connect(self):
#         pass
#
#     def on_disconnect(self):
#         pass
#
#     def exposed_register_manager(self):
#         SimpleDispatcherService.exposed_manager_root = self._conn.root
#
# if __name__ == "__main__":
#     from rpyc.utils.server import ThreadedServer
#     t = ThreadedServer(SimpleDispatcherService, port=18861,
#                        protocol_config = {"allow_public_attrs" : True})
#     t.start()


import time,pickle
import zmq
from eu.hriechmann.distributed_process_manager.common import Message, ClientCommands, ManagerCommands, ServerCommands

class Server(object):

    def __init__(self, client_port, manager_port):
        self.managers = []
        self.clients = []

        self.context = zmq.Context()
        self.client_socket = self.context.socket(zmq.ROUTER)
        self.manager_socket = self.context.socket(zmq.ROUTER)
        self.client_socket.bind("tcp://*:"+str(client_port))
        self.manager_socket.bind("tcp://*:"+str(manager_port))

        self.poll = zmq.Poller()
        self.poll.register(self.client_socket, zmq.POLLIN)
        self.poll.register(self.manager_socket, zmq.POLLIN)

    def run(self):
        while True:
            sockets = dict(self.poll.poll())
            new_messages = []
            if self.client_socket in sockets:
                ident, msg = self.client_socket.recv_multipart()
                print('Server received %s id %s' % (msg, ident))
                message = pickle.loads(msg)
                print("Received request: %s" % message)
                new_messages += self.process_client_msg(message, ident)
            if self.manager_socket in sockets:
                ident, msg = self.manager_socket.recv_multipart()
                print('Server received manager %s id %s' % (msg, ident))
                message = pickle.loads(msg)
                print("Received request: %s" % message)
                new_messages += self.process_manager_msg(message, ident)
            for (id, message) in new_messages:
                if id in self.managers:
                    print("Sending message to manager: ", id, message)
                    self.manager_socket.send_multipart([id, pickle.dumps(message)])
                elif id in self.clients:
                    print("Sending message to client: ", id, message)
                    self.client_socket.send_multipart([id, pickle.dumps(message)])
                else:
                    raise Exception("Unknown receiver")

    def process_client_msg(self, message, sender):
        ret = []
        if message.command == ClientCommands.REGISTER:
            self.clients.append(sender)
            print("Client was registered", sender)
        else:
            if message.receiver == "":
                receivers = self.managers
            else:
                receivers = [message.receiver, ]
            for receiver in receivers:
                ret.append((receiver, message))
        return ret

    def process_manager_msg(self, message, sender):
        ret = []
        if message.command == ManagerCommands.REGISTER:
            self.managers.append(sender)
            print("Manager was registered", sender)
            for client in self.clients:
                ret.append((sender, Message(sender, ServerCommands.NEW_CLIENT, client)))
        elif message.receiver in self.clients:
            ret.append((message.receiver, message))

        return ret


if __name__ == "__main__":
    myServer = Server(5555, 5556)
    myServer.run()