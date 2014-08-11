__author__ = 'hriechma'
import sys
sys.path.append("src/")
from eu.hriechmann.distributed_process_manager import server
myServer = server.Server("configs/server.cfg")
myServer.run()