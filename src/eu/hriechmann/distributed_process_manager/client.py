__author__ = 'hriechma'

import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
import pickle
import tempfile
import os
import subprocess
import configparser
import logging
from itertools import islice
from eu.hriechmann.distributed_process_manager.common import \
    Message, ClientCommands, ManagerCommands, ProcessStati, \
    ServerCommands


#from http://stackoverflow.com/questions/260273/
# most-efficient-way-to-search-the-last-x-lines-of-a-file-in-python/260433#260433
def reversed_lines(file, last_pos):
    """Generate the lines of file in reverse order."""
    part = ''
    for block in reversed_blocks(file, last_pos):
        for c in reversed(block):
            if c == '\n' and part:
                yield part[::-1]
                part = ''
            part += c
    if part:
        yield part[::-1]


def reversed_blocks(file, last_pos, blocksize=4096):
    """Generate blocks of file's contents in reverse order."""
    file.seek(0, os.SEEK_END)
    here = file.tell()
    while last_pos < here:
        delta = min(blocksize, here)
        here -= delta
        file.seek(here, os.SEEK_SET)
        yield file.read(delta)


class Client(object):
    def __init__(self, config_file):
        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
        self.config = configparser.ConfigParser()
        print(self.config.read([config_file, ]))
        self.id = self.config.get("main", "id")
        self.context = zmq.Context()
        self.server = self.config.get("main", "server")
        self.port = self.config.get("main", "port")
        self.use_encryption = self.config.getboolean("main", "use_encryption")
        print("Using encryption: ", self.use_encryption)
        if self.config.has_section("allowed_processes"):
            self.allowed_process = {}
            for (name, value) in self.config.items("allowed_processes"):
                self.allowed_process[name] = value

        self.process_desc = []
        self.local_processes = {}

    def run(self):
        # Socket to talk to server
        print("Connecting to server "+self.server+" on port: "+str(self.port))

        if self.use_encryption:
            print("Using encryption")
            base_dir = os.getcwd()
            public_keys_dir = os.path.join(base_dir, 'certificates')
            secret_keys_dir = os.path.join(base_dir, 'keys')

            # # Start an authenticator for this context.
            # auth = ThreadAuthenticator(self.context)
            # auth.start()
            # auth.allow('127.0.0.1')
            # # Tell authenticator to use the certificate in a directory
            # auth.configure_curve(domain='*', location=public_keys_dir)

            client_secret_file = os.path.join(secret_keys_dir, "client.key_secret")
            client_public, client_secret = zmq.auth.load_certificate(client_secret_file)

            socket = self.context.socket(zmq.DEALER)
            socket.curve_secretkey = client_secret
            socket.curve_publickey = client_public
            server_public_file = os.path.join(public_keys_dir, "server.key")
            server_public, _ = zmq.auth.load_certificate(server_public_file)
            # The client must know the server's public key to make a CURVE connection.
            socket.curve_serverkey = server_public
        else:
            socket = self.context.socket(zmq.DEALER)

        identity = str(self.id)
        socket.identity = identity.encode('ascii')
        socket.connect("tcp://"+self.server+":"+str(self.port))

        # Register with server
        message = Message("", ClientCommands.REGISTER)
        print("Sending request %s …" % message)
        socket.send(pickle.dumps(message))

        while True:
            #Wait for commands
            poll = zmq.Poller()
            poll.register(socket, zmq.POLLIN)
            sockets = {}
            while not socket in sockets:
                sockets = dict(poll.poll(1000))
                new_messages = self.check_processes()
                for new_message in new_messages:
                    socket.send(pickle.dumps(new_message))
            message = socket.recv()
            new_messages = self.process_message(pickle.loads(message))
            for new_message in new_messages:
                socket.send(pickle.dumps(new_message))

    def process_message(self, message):
        if message.command != ServerCommands.SEND_KEEPALIVE:
            print("Received message", message.command)
        ret = []
        if message.command == ServerCommands.SEND_KEEPALIVE:
            ret.append(Message("", ClientCommands.KEEPALIVE))
        elif message.command == ManagerCommands.INIT_PROCESS:
            print("I need to supervise process:", message.payload)
            new_process = message.payload
            if hasattr(self, "allowed_process"):
                if not new_process.id.lower() in self.allowed_process or \
                    self.allowed_process[new_process.id.lower()] != os.path.join(
                        new_process.working_directory, new_process.command):
                    ###TODO send reject process message to manager
                    print("My config forbids me to execute this process", self.allowed_process)
                else:
                    self.process_desc.append(new_process)
            else:
                self.process_desc.append(new_process)
        elif message.command == ManagerCommands.START_PROCESS:
            self.start_process(message.payload)
        elif message.command == ManagerCommands.STOP_PROCESS:
            self.stop_process(message.payload)
        elif message.command == ManagerCommands.SEND_LOGS:
            ret += self.send_process_out(message.payload)
        else:
            raise Exception("Unknown ManagerCommand in client")
        return ret

    def start_process(self, process_id):
        for process in self.process_desc:
            if process.id == process_id:
                temp_dir = tempfile.TemporaryDirectory(prefix=process.id)
                std_out_file = open(os.path.join(temp_dir.name, "std_out"), 'w')
                std_err_file = open(os.path.join(temp_dir.name, "std_err"), 'w')
                print(process.env)
                try:
                    self.local_processes[process.id] = [subprocess.Popen(process.command, cwd=process.working_directory,
                                                                     env=process.env, stdout=std_out_file, stderr=std_err_file), ProcessStati.INIT, temp_dir, 0, 0]
                except OSError as e:
                    print("Starting process failed: ", process.id, "with ", e)
                    #TODO

    def stop_process(self, process_id):
        print("Trying to stop process: ", process_id)
        self.local_processes[process_id][0].terminate()
        self.local_processes[process_id][1] = ProcessStati.STOPPING

    def send_process_out(self, process_id):
        process_data = self.local_processes[process_id]
        # grab file content
        std_out_data = "".join(islice(reversed_lines(open(os.path.join(process_data[2].name, "std_out")),
                                                     process_data[3]), 10))
        std_err_data = "".join(islice(reversed_lines(open(os.path.join(process_data[2].name, "std_err")),
                                                     process_data[4]), 10))
        process_data[3] += len(std_out_data)
        process_data[4] += len(std_err_data)
        return [Message("", ClientCommands.PROCESS_LOGS, (process_id, std_out_data, std_err_data)), ]

    def check_processes(self):
        ret = []
        for process_id in self.local_processes:
            last_status = self.local_processes[process_id][1]
            new_status = ProcessStati.INIT
            if self.local_processes[process_id][0].poll() is None:
                print("Process ", process_id, "is still running")
                new_status = ProcessStati.RUNNING
            elif last_status == ProcessStati.STOPPING or last_status == ProcessStati.STOPPED:
                new_status = ProcessStati.STOPPED
            else:
                if last_status != ProcessStati.KILLED:
                    print("Process ", process_id, "died")
                new_status = ProcessStati.KILLED
            if last_status != new_status:
                self.local_processes[process_id][1] = new_status
                ret.append(Message("", ClientCommands.PROCESSSTATUS_CHANGED, (process_id, new_status)))
        return ret
#



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    myClient = Client("../configs/client.cfg")
    myClient.run()
