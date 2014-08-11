__author__ = 'hriechma'
import sys
sys.path.append("src/")
from PySide.QtGui import QApplication
from eu.hriechmann.distributed_process_manager import manager, manager_gui
if len(sys.argv) <= 3:
    print("Usage: python start_manager.py <configfilename> <server-hostname> <server-port>")
    sys.exit(-1)
import socket
hostname = socket.getfqdn()
myManager = manager.Manager(hostname+"-manager", sys.argv[1], sys.argv[2], int(sys.argv[3]))
myManager.start()
app = QApplication(sys.argv)
frame = manager_gui.MainWindow(myManager)
frame.show()
ret = app.exec_()
myManager.issue_command("TERMINATE_MANAGER", "0")
sys.exit(ret)
