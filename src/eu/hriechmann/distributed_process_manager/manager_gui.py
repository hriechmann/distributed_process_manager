__author__ = 'hriechma'

import sys
import platform
import PySide
from PySide.QtCore import QRect, QTimer, SIGNAL
from PySide.QtGui import QApplication, QMainWindow, QPushButton,\
    QWidget, QGridLayout, QLabel
from eu.hriechmann.distributed_process_manager.manager import Manager
from eu.hriechmann.distributed_process_manager.common import ManagerCommands, ProcessStati



class MainWindow(QMainWindow):
    def __init__(self, process_manager):
        super(MainWindow, self).__init__(None)
        self.resize(731, 475)
        central_widget = QWidget(self)
        grid_layout = QGridLayout(central_widget)
        self.my_widgets = {}
        for id, process in enumerate(process_manager.get_process_descriptions()):
            name_label = QLabel(self)
            name_label.setText(process.id)
            grid_layout.addWidget(name_label, id, 0, 1, 1)
            status_label = QLabel(self)
            status_label.setText(ProcessStati.INIT.name)
            grid_layout.addWidget(status_label, id, 1, 1, 1)
            start_button = QPushButton(self)
            start_button.setText("Start "+process.id)
            start_button.clicked.connect(self.button_clicked)
            grid_layout.addWidget(start_button, id, 2, 1, 1)
            log_button = QPushButton(self)
            log_button.setText("Update-log "+process.id)
            log_button.clicked.connect(self.log_button_clicked)
            grid_layout.addWidget(log_button, id, 3, 1, 1)
            log_out_label = QLabel(self)
            log_out_label.setText("")
            grid_layout.addWidget(log_out_label, id, 4, 1, 1)
            log_err_label = QLabel(self)
            log_err_label.setText("")
            grid_layout.addWidget(log_err_label, id, 5, 1, 1)
            self.my_widgets[process.id] = [name_label, status_label, start_button, log_button, log_out_label, log_err_label]
        self.setCentralWidget(central_widget)

        self.process_manager = process_manager
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

    def log_button_clicked(self):
        wanted_process = self.sender().text().split(" ")[1]
        self.process_manager.issue_command(ManagerCommands.SEND_LOGS, wanted_process)

    def update_stati(self):
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
            widgets[4].setText(process.log_out)
            widgets[5].setText(process.log_err)




if __name__ == '__main__':
    myManager = Manager("otho-manager", "otho", 5556)
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