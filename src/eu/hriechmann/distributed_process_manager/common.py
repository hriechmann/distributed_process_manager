__author__ = 'hriechma'

from enum import Enum
import hashlib
import os

ManagerCommands = Enum("ManagerCommands", "REGISTER INIT_PROCESS START_PROCESS STOP_PROCESS SEND_LOGS")
ClientCommands = Enum("ClientCommands", "REGISTER PROCESSSTATUS_CHANGED PROCESS_LOGS")
ServerCommands = Enum("ServerCommands", "NEW_CLIENT")
ProcessStati = Enum("ProcessStati", "INIT RUNNING STOPPING STOPPED FAILED KILLED")

class Message(object):

    def __init__(self, receiver, command, payload=None):
        self.receiver = receiver
        self.command = command
        self.payload = payload

    def __str__(self):
        return "Message to "+str(self.receiver)+". Command is: "+str(self.command)

class ProcessDescription(object):

    def __init__(self, id, target_host, command, working_directory="", env={}):
        self.id = id
        self.target_host  = target_host
        self.command = command
        self.working_directory = working_directory
        self.env = env

    def __str__(self):
        return "Process: "+str(self.id)+"to be executed on host: "+self.target_host+"Command: "+self.command

class ProcessStatus(object):

    def __init__(self, responsible_client, process_desc):
        self.responsible_client = responsible_client
        self.process_desc = process_desc
        self.status = ProcessStati.INIT
        self.log_out = ""
        self.log_err = ""

    def __str__(self):
        return "ProcessStatues: Process: "+str(self.process_desc)+" on client: "+\
               str(self.responsible_client)+" has status: "+self.status
           
           
BLOCKSIZE = 65536
MAX_SIZE = 1024*1024*100

class IncrementalFileReaderAndHasher(object):
    
    def __init__(self, filename):
        self.hasher = hashlib.sha1()
        self.filename = filename
        statinfo = os.stat(self.filename)
        self.big_file = statinfo > MAX_SIZE
        if self.big_file:
            self.file_contents = None
            buf = afile.read(BLOCKSIZE)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(BLOCKSIZE)
        else:
            afile = open(self.filename,'ab')
            self.file_contents = afile.read()
            self.hasher.update(self.file_contents)
        
    def hash(self):
        return self.hasher.hexdigest()
        
    def get_file_contents(self):
        if self.big_file:
            TODO
        else:
            return self.file_contents