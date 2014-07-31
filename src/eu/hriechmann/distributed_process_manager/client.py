__author__ = 'hriechma'

import zmq
import pickle
import tempfile
import os
import subprocess
from itertools import islice
from eu.hriechmann.distributed_process_manager.common import \
    Message, ClientCommands, ManagerCommands, ProcessStati


#from http://stackoverflow.com/questions/260273/
# most-efficient-way-to-search-the-last-x-lines-of-a-file-in-python/260433#260433
def reversed_lines(file):
    "Generate the lines of file in reverse order."
    part = ''
    for block in reversed_blocks(file):
        for c in reversed(block):
            if c == '\n' and part:
                yield part[::-1]
                part = ''
            part += c
    if part: yield part[::-1]


def reversed_blocks(file, blocksize=4096):
    "Generate blocks of file's contents in reverse order."
    file.seek(0, os.SEEK_END)
    here = file.tell()
    while 0 < here:
        delta = min(blocksize, here)
        here -= delta
        file.seek(here, os.SEEK_SET)
        yield file.read(delta)


class Client(object):

    def __init__(self, id, server, port):
        self.id = id
        self.context = zmq.Context()
        self.server = server
        self.port = port
        self.process_desc = []
        self.local_processes = {}

    def run(self):
        # Socket to talk to server
        print("Connecting to server…"+self.server+" on port: "+str(self.port))
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
        print("Received message",message.command)
        ret = []
        if message.command == ManagerCommands.INIT_PROCESS:
            print("I need to supervise process:", message.payload)
            self.process_desc.append(message.payload)
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
                env = {"LD_LIBRARY_PATH": "/media/local/hriechma/redmine-git/libubici/", "DISPLAY": ":0",
                       "HOME": "/homes/hriechma"}
                self.local_processes[process.id] = [subprocess.Popen(process.command, cwd=process.working_directory,
                                                                     env=env, stdout=std_out_file, stderr=std_err_file), ProcessStati.INIT, temp_dir]

    def stop_process(self, process_id):
        print("Trying to stop process: ", process_id)
        self.local_processes[process_id][0].terminate()
        self.local_processes[process_id][1] = ProcessStati.STOPPING

    def send_process_out(self, process_id):
        process_data = self.local_processes[process_id]
        # grab file content
        std_out_data = "".join(islice(reversed_lines(open(os.path.join(process_data[2].name, "std_out"))), 10))
        std_err_data = "".join(islice(reversed_lines(open(os.path.join(process_data[2].name, "std_err"))), 10))
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
    myClient = Client("otho", "otho", 5555)
    myClient.run()
