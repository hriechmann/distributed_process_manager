__author__ = 'hriechma'

import time
import pickle
import os
import logging
import configparser
import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
from eu.hriechmann.distributed_process_manager.common import Message, ClientCommands, ManagerCommands, ServerCommands


class Server(object):

    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        print(self.config.read([config_file, ]))
        self.client_port = self.config.getint("main", "client_port")
        self.manager_port = self.config.getint("main", "manager_port")
        self.use_encryption = self.config.getboolean("main", "use_encryption")
        self.managers = {}
        self.clients = {}

        self.context = zmq.Context()

        if self.use_encryption:
            base_dir = os.getcwd()
            public_keys_dir = os.path.join(base_dir, 'certificates')
            secret_keys_dir = os.path.join(base_dir, 'keys')
            # Start an authenticator for this context.
            self.auth = ThreadAuthenticator(self.context)
            self.auth.start()
            #self.auth.allow('127.0.0.1')
            # Tell authenticator to use the certificate in a directory
            self.auth.configure_curve(domain='*', location=public_keys_dir)

            server_secret_file = os.path.join(secret_keys_dir, "server.key_secret")
            server_public, server_secret = zmq.auth.load_certificate(server_secret_file)

            self.client_socket = self.context.socket(zmq.ROUTER)
            self.client_socket.curve_secretkey = server_secret
            self.client_socket.curve_publickey = server_public
            self.client_socket.curve_server = True  # must come before bind
        else:
            self.client_socket = self.context.socket(zmq.ROUTER)

        self.client_socket.bind("tcp://*:"+str(self.client_port))

        self.manager_socket = self.context.socket(zmq.ROUTER)
        self.manager_socket.bind("tcp://*:"+str(self.manager_port))

        self.poll = zmq.Poller()
        self.poll.register(self.client_socket, zmq.POLLIN)
        self.poll.register(self.manager_socket, zmq.POLLIN)

    def run(self):
        while True:
            sockets = dict(self.poll.poll(1000))
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
            if self.managers:
                print("Keepalive: ", self.clients)
                print("Keepalive: ", self.managers)
                for client in list(self.clients.keys()):
                    message = Message(client, ServerCommands.SEND_KEEPALIVE)
                    self.client_socket.send_multipart([client, pickle.dumps(message)])
                    if self.clients[client] >= 10:
                        del self.clients[client]
                        for manager in self.managers:
                            manager_message = Message(manager,ServerCommands.LOST_CLIENT, client)
                            self.manager_socket.send_multipart([manager, pickle.dumps(manager_message)])
                    else:
                        self.clients[client] += 1
                for manager in list(self.managers.keys()):
                    message = Message(manager, ServerCommands.SEND_KEEPALIVE)
                    self.manager_socket.send_multipart([manager, pickle.dumps(message)])
                    if self.managers[manager] >= 10:
                        del self.managers[manager]
                    else:
                        self.managers[manager] += 1



    def process_client_msg(self, message, sender):
        ret = []
        if message.command == ClientCommands.REGISTER:
            self.clients[sender] = 0
            print("Client was registered", sender)
            for manager in self.managers:
                ret.append((manager, Message("", ServerCommands.NEW_CLIENT, sender)))
        elif message.command == ClientCommands.KEEPALIVE:
            self.clients[sender] = 0
        else:
            if message.receiver == "":
                receivers = self.managers.keys()
            else:
                receivers = [message.receiver, ]
            for receiver in receivers:
                ret.append((receiver, message))
        return ret

    def process_manager_msg(self, message, sender):
        ret = []
        if message.command == ManagerCommands.REGISTER:
            self.managers[sender] = 0
            print("Manager was registered", sender)
            for client in self.clients:
                ret.append((sender, Message(sender, ServerCommands.NEW_CLIENT, client)))
        elif message.command == ManagerCommands.KEEPALIVE:
            self.managers[sender] = 0
        elif message.receiver in self.clients:
            ret.append((message.receiver, message))

        return ret


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    myServer = Server(5555, 5556)
    myServer.run()


