__author__ = 'hriechma'

from enum import Enum

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