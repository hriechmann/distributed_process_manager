from pkg_resources import yield_lines

__author__ = 'hriechma'

import sys
from PySide.QtCore import QRect, QTimer, SIGNAL
from PySide.QtGui import QApplication, QMainWindow, QPushButton,\
    QWidget, QGridLayout, QLabel, QDialog
from eu.hriechmann.distributed_process_manager.manager import Manager
from eu.hriechmann.distributed_process_manager.common import ManagerCommands, \
    ProcessStati, ClientStati


class ClientStartDialog(QDialog):
    def __init__(self, parent, clients):
        super(ClientStartDialog, self).__init__(parent)
        grid_layout = QGridLayout(self)
        xpos = 0
        ypos = 0
        for client in clients:
            if client.status == ClientStati.NOT_RUNNING:
                start_button = QPushButton(self)
                start_button.setText(client.hostname.decode("utf-8"))
                start_button.clicked.connect(self.start_button_clicked)
                grid_layout.addWidget(start_button, ypos, xpos, 1, 1)
                xpos += 1
        self.clients = clients

    def start_button_clicked(self):
        print("QDialog Start Button clicked")
        wanted_client = self.sender().text().encode("ascii")
        for client in self.clients:
            if client.hostname == wanted_client:
                print("Wanted client: ", client)
                from plumbum import SshMachine
                print(client.local_path)
                remote = SshMachine(client.hostname.decode("utf-8"))
                if client.local_path != "":
                    remote.cwd.chdir(client.local_path)
                #start_client = remote["/bin/bash"]
                #start_client.run(["./bin/start_client", "otho", "5555"]) #TODO
                #start_client = remote["./bin/start_client"]
                #start_client.run(["otho", "5555"]) #TODO
                remote.popen(args=["./bin/start_client", "otho", "5555"])#, ssh_opts=("-f",))#TODO server_name port
        print("Starting done")


class ProcessStatusDialog(QDialog):
    def __init__(self, parent):
        super(ProcessStatusDialog, self).__init__(parent)
        grid_layout = QGridLayout(self)
        xpos = 0
        ypos = 0
        self.log_out_label = QLabel(self)
        self.log_out_label.setText("")
        grid_layout.addWidget(self.log_out_label, ypos, xpos, 1, 1)
        xpos += 1
        self.log_err_label = QLabel(self)
        self.log_err_label.setText("")
        grid_layout.addWidget(self.log_err_label, ypos, xpos, 1, 1)
        xpos += 1
        self.finished.connect(parent.status_dialog_closed)
        self.show()


class MainWindow(QMainWindow):
    def __init__(self, process_manager):
        super(MainWindow, self).__init__(None)
        self.resize(731, 475)
        central_widget = QWidget(self)
        grid_layout = QGridLayout(central_widget)
        self.clients_label = QLabel(self)
        self.clients_label.setText("Connected clients: ")
        grid_layout.addWidget(self.clients_label, 0, 0, 1, 1)
        start_clients_button = QPushButton(self)
        start_clients_button.setText("Start Clients")
        start_clients_button.clicked.connect(self.start_clients_clicked)
        grid_layout.addWidget(start_clients_button, 0, 1, 1, 1)

        self.my_widgets = {}
        for id, process in enumerate(process_manager.get_process_descriptions()):
            xpos = 0
            ypos = id+1
            name_label = QLabel(self)
            name_label.setText(process.id)
            grid_layout.addWidget(name_label, ypos, xpos, 1, 1)
            xpos += 1
            host_label = QLabel(self)
            host_label.setText(process.target_host)
            grid_layout.addWidget(host_label, ypos, xpos, 1, 1)
            xpos += 1
            status_label = QLabel(self)
            status_label.setText(ProcessStati.INIT.name)
            grid_layout.addWidget(status_label, ypos, xpos, 1, 1)
            xpos += 1
            start_button = QPushButton(self)
            start_button.setText("Start "+process.id)
            start_button.clicked.connect(self.button_clicked)
            grid_layout.addWidget(start_button, ypos, xpos, 1, 1)
            xpos += 1
            log_button = QPushButton(self)
            log_button.setText("Update-log "+process.id)
            log_button.clicked.connect(self.log_button_clicked)
            grid_layout.addWidget(log_button, ypos, xpos, 1, 1)
            xpos += 1
            self.my_widgets[process.id] = [name_label, status_label, start_button, log_button]
        self.setCentralWidget(central_widget)

        self.clients = process_manager.get_client_stati()
        self.start_clients_dialog = ClientStartDialog(self, self.clients)

        self.process_manager = process_manager

        self.status_dialogs = {}

        timer = QTimer(self)
        self.connect(timer, SIGNAL("timeout()"), self.update_stati)
        timer.start(1000)

    def button_clicked(self):
        print("Start Button clicked")
        button_command = self.sender().text().split(" ")[0]
        wanted_process = self.sender().text().split(" ")[1]
        if button_command == "Start":
            command = ManagerCommands.START_PROCESS
        elif button_command == "Stop":
            command = ManagerCommands.STOP_PROCESS
        else:
            raise Exception("Unknown Button Command")
        self.process_manager.issue_command(command, wanted_process)

    def start_clients_clicked(self):
        self.start_clients_dialog.open()

    def log_button_clicked(self):
        wanted_process = self.sender().text().split(" ")[1]
        self.status_dialogs[wanted_process] = ProcessStatusDialog(self)

    def status_dialog_closed(self):
        for k, v in self.status_dialogs.items():
            if v == self.sender():
                del self.status_dialogs[k]
                print("Found status dialog to delete")

    def update_stati(self):
        self.clients = self.process_manager.get_client_stati()
        print(self.clients)
        self.clients_label.setText("Connected clients: ")
        for client in self.clients:
            prev_text = self.clients_label.text()
            if client.status == ClientStati.RUNNING:
                #self.clients_label.setStyleSheet("QLabel { background-color : green}")
                color_text = """<span style="color:green">"""
            else:
                #self.clients_label.setStyleSheet("QLabel { background-color : red}")
                color_text = """<span style="color:red">"""
            self.clients_label.setText(prev_text+" "+color_text+client.hostname.decode("utf-8")+"</span>,")

        process_stati = self.process_manager.get_process_stati()
        for process in process_stati:
            widgets = self.my_widgets[process.process_desc.id]
            widgets[1].setText(process.status.name)
            if process.status in (ProcessStati.INIT, ProcessStati.KILLED, ProcessStati.STOPPED, ProcessStati.STOPPING):
                widgets[2].setText("Start "+process.process_desc.id)
            elif process.status in (ProcessStati.RUNNING, ):
                widgets[2].setText("Stop "+process.process_desc.id)
            else:
                raise Exception("Unknown process status"+process.status.name)
            if process.process_desc.id in self.status_dialogs:
                self.status_dialogs[process.process_desc.id].log_out_label.setText(process.log_out)
                self.status_dialogs[process.process_desc.id].log_err_label.setText(process.log_err)
        for log_dialog in self.status_dialogs:
            print("requesting logs for ", log_dialog)
            self.process_manager.issue_command(ManagerCommands.SEND_LOGS, log_dialog)




if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print("Usage: python manager_gui.py <configfilename>")
        sys.exit(-1)
    myManager = Manager("otho-manager", sys.argv[1], "otho", 5556)
    myManager.start()
    app = QApplication(sys.argv)
    frame = MainWindow(myManager)
    frame.show()
    ret = app.exec_()
    myManager.issue_command("TERMINATE_MANAGER", "0")
    sys.exit(ret)



#         # textEdit needs to be a class variable.
#         self.textEdit = QTextEdit(centralwidget)
#         gridLayout.addWidget(self.textEdit, 0, 0, 1, 1)
#         self.setCentralWidget(centralwidget)
#         menubar = QMenuBar(self)
#         menubar.setGeometry(QRect(0, 0, 731, 29))
#         menu_File = QMenu(menubar)
#         self.setMenuBar(menubar)
#         statusbar = QStatusBar(self)
#         self.setStatusBar(statusbar)
#         actionShow_GPL = QAction(self)
#         actionShow_GPL.triggered.connect(self.showGPL)
#         action_About = QAction(self)
#         action_About.triggered.connect(self.about)
#         iconToolBar = self.addToolBar("iconBar.png")
# #------------------------------------------------------
# # Add icons to appear in tool bar - step 1
#         actionShow_GPL.setIcon(QIcon(":/showgpl.png"))
#         action_About.setIcon(QIcon(":/about.png"))
#         action_Close = QAction(self)
#         action_Close.setCheckable(False)
#         action_Close.setObjectName("action_Close")
#         action_Close.setIcon(QIcon(":/quit.png"))
# #------------------------------------------------------
# # Show a tip on the Status Bar - step 2
#         actionShow_GPL.setStatusTip("Show GPL Licence")
#         action_About.setStatusTip("Pop up the About dialog.")
#         action_Close.setStatusTip("Close the program.")
# #------------------------------------------------------
#         menu_File.addAction(actionShow_GPL)
#         menu_File.addAction(action_About)
#         menu_File.addAction(action_Close)
#         menubar.addAction(menu_File.menuAction())
#
#         iconToolBar.addAction(actionShow_GPL)
#         iconToolBar.addAction(action_About)
#         iconToolBar.addAction(action_Close)
#         action_Close.triggered.connect(self.close)
#
#     def showGPL(self):
#         '''Read and display GPL licence.'''
#         self.textEdit.setText(open('COPYING.txt').read())
#
#     def about(self):
#         '''Popup a box with about message.'''
#         QMessageBox.about(self, "About PyQt, Platform and the like",
#                 """<b> About this program </b> v %s
#                <p>Copyright � 2011 Your Name.
#                All rights reserved in accordance with
#                GPL v2 or later - NO WARRANTIES!
#                <p>This application can be used for
#                displaying OS and platform details.
#                <p>Python %s - PySide version %s - Qt version %s on %s""" % \
#                 (__version__, platform.python_version(), PySide.__version__,\
#                  PySide.QtCore.__version__, platform.system()))