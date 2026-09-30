import os
import sys
import base64
import threading
import queue
import re
from PyQt6.QtWidgets import (QApplication, QMessageBox, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGroupBox, QLabel, QLineEdit, QFileDialog,
                             QPushButton, QTabWidget, QFormLayout, QTextEdit,
                             QSpinBox, QCheckBox, QGridLayout, QSizePolicy, QFrame, QDoubleSpinBox, QComboBox)
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, Qt, QThread, QMutex, QWaitCondition, QTimer,QRegularExpression
from PyQt6.QtGui import QFont, QIntValidator,QValidator, QPalette, QColor
import paramiko
from paramiko.channel import Channel
import time
import yaml
import json

from pyparsing import line_end


class DialogResult:
    def __init__(self):
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.value = None

class InteractiveSSHWorker(QObject):
    log_signal = pyqtSignal(str,bool)
    buttons_state_signal = pyqtSignal(str)
    request_decision = pyqtSignal(DialogResult,str,str)
    update_entry = pyqtSignal(dict)
    finished_signal = pyqtSignal()  # Вызывается только при полном отключении

    def __init__(self,host,port,jump_flag,jump_host,jump_port,jump_user,jump_pass,user,secret):
        super().__init__()
        self.task_queue = queue.Queue()
        self.is_running = True
        self.ssh_connected = False

        self.jump_client = paramiko.SSHClient()
        self.jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.jump_hostTransport = self.jump_client.get_transport()
        self.jump_hostChannel = Channel(1)
        self.jump_flg = jump_flag
        self.jump_host = jump_host
        self.jump_port = jump_port
        self.jump_user = jump_user
        self.jump_pass = jump_pass
        self.sftpTransport = self.client.get_transport()
        self.sftpClient = paramiko.SFTPClient
        self.host = host
        self.port = port
        self.username = user
        self.userpass = secret
        self.load_progress = 0
        self.file_tail = ''
        self.direction = ''
        self.ServerHostname = ''
        self.ConnectedState = False
        self.KeepAlive = 10

        self.default_settings = {'DeviceIpAddr1': "192.168.88.137", 'DeviceIpAddr2': "192.168.188.137",
                         'DHCP1': False, 'DHCP2': False,
                         'MacAddr1': f"FA:CE:80:4A:00:00",
                         'MacAddr2': f"FA:CE:80:4B:00:00",
                         'DeviceIpMask1': "255.255.255.0", 'DeviceIpMask2': "255.255.255.0",
                         'ServerIpAddrA1': "192.168.88.10", 'ServerIpAddrA2': "192.168.188.10",
                         'ServerIpAddrB1': "192.168.88.11", 'ServerIpAddrB2': "192.168.188.11",
                         'ServersIpMask1': "255.255.255.0", 'ServersIpMask2': "255.255.255.0",
                         'ServerJsonPortA': int(15351), 'ServerJsonPortB': int(15351),
                         'ServerSecureTCP': False, 'DeviceID': "TR8040000",
                         'DeviceIpGW1': "", 'DeviceIpGW2': "",
                         'TimeServers': "", 'DectActiveControl': False,
                         'AMEnabled': False,
                         'AMLevelOverflow': 0.0, 'AMNominalLevel': 0.0,
                         'AMSilenceAudioThreshold': -52.0, 'AMSilenceCountThreshold': 3000,
                         'UartUL2': False, 'UseGW4': False}

        self.main_settings = {'DeviceIpAddr1': "192.168.88.137", 'DeviceIpAddr2': "192.168.188.137",
                         'DHCP1': False, 'DHCP2': False,
                         'MacAddr1': f"FA:CE:80:4A:00:00",
                         'MacAddr2': f"FA:CE:80:4B:00:00",
                         'DeviceIpMask1': "255.255.255.0", 'DeviceIpMask2': "255.255.255.0",
                         'ServerIpAddrA1': "192.168.88.10", 'ServerIpAddrA2': "192.168.188.10",
                         'ServerIpAddrB1': "192.168.88.11", 'ServerIpAddrB2': "192.168.188.11",
                         'ServersIpMask1': "255.255.255.0", 'ServersIpMask2': "255.255.255.0",
                         'ServerJsonPortA': int(15351), 'ServerJsonPortB': int(15351),
                         'ServerSecureTCP': False, 'DeviceID': "TR8040000",
                         'DeviceIpGW1': "", 'DeviceIpGW2': "",
                         'TimeServers': "", 'DectActiveControl': False,
                         'AMEnabled': False,
                         'AMLevelOverflow': 0.0, 'AMNominalLevel': 0.0,
                         'AMSilenceAudioThreshold': -52.0, 'AMSilenceCountThreshold': 3000,
                         'UartUL2': False, 'UseGW4': False}
        self.current_settings = {'DeviceIpAddr1': '', 'DeviceIpAddr2': '',
                            'DHCP1': False, 'DHCP2': False,
                            'MacAddr1': '', 'MacAddr2': '',
                            'DeviceIpMask1': '', 'DeviceIpMask2': '',
                            'ServerIpAddrA1': '', 'ServerIpAddrA2': '',
                            'ServerIpAddrB1': '', 'ServerIpAddrB2': '',
                            'ServersIpMask1': '', 'ServersIpMask2': '',
                            'ServerJsonPortA': 0, 'ServerJsonPortB': 0,
                            'DeviceID': '', 'ServerSecureTCP': False,
                            'DeviceIpGW1': '', 'DeviceIpGW2': '',
                            'TimeServers': '', 'DectActiveControl': False,
                            'AMEnabled': False,
                            'AMLevelOverflow': 0.0, 'AMNominalLevel': 0.0,
                            'AMSilenceAudioThreshold': -52.0, 'AMSilenceCountThreshold': 3000,
                            'UartUL2': False}

    def connect(self, host=None,port=None, jump_flag=None, jump_host=None, jump_port=None, jump_user=None,
                jump_pass=None, user=None, secret=None):
        self.username = user if user is not None else self.username
        self.userpass = secret if user is not None else self.userpass
        self.host = host if host is not None else self.host
        self.port = port if port is not None else self.port
        self.jump_flg = jump_flag if jump_flag is not None else self.jump_flg
        self.jump_host = jump_host if jump_host is not None else self.jump_host
        self.jump_port = jump_port if jump_port is not None else self.jump_port
        self.jump_user = jump_user if jump_user is not None else self.jump_user
        self.jump_pass = jump_pass if jump_pass is not None else self.jump_pass
        self.send_log_string(f"Starting ssh({self.username})")
        if self.jump_flg:
            self.send_log_string(f"Connecting via jump host {self.jump_host}")
            self.send_log_string(f"[Local]--->ssh--->")
            try:
                self.jump_client.connect(hostname=self.jump_host, username=self.jump_user, password=self.jump_pass, port=self.jump_port,
                                       timeout=10)
            except Exception as exc:
                self.send_log_string(f"Can't connect to Jump host. {exc}")
            else:
                self.send_log_string(f"[Local]--->ssh--->{self.jump_host}--->",True)
                try:
                    self.jump_hostTransport = self.jump_client.get_transport()
                    self.jump_hostChannel = self.jump_hostTransport.open_channel("direct-tcpip", (self.host, self.port),
                                                                                 (self.jump_host, self.port), timeout=10)
                except Exception as exc:
                    self.send_log_string(f"Can't create channel to host. {exc}")
                else:
                    self.send_log_string(f"[Local]--->ssh--->{self.jump_host}--->tunnel--->",True)
                    try:
                        self.client.connect(hostname=self.host, username=self.username, password=self.userpass, sock=self.jump_hostChannel,
                                            timeout=10)
                    except Exception as exc:
                        self.send_log_string(f"Can't connect via jump host. {exc}")
                    else:
                        self.client.get_transport().set_keepalive(self.KeepAlive)
                        self.send_log_string(f"[Local]--->ssh--->{self.jump_host}--->tunnel--->ssh--->[device]",True)

        else:
            try:
                self.client.connect(hostname=self.host, username=self.username, password=self.userpass, timeout=10)
            except Exception as exc:
                self.send_log_string(f"Can't connect. {exc}")
                self.client.close()
            else:
                self.client.get_transport().set_keepalive(self.KeepAlive)

    def close(self):
        if self.jump_flg:
            self.jump_client.close()
        self.client.close()
        self.ServerHostname = ''
        self.send_log_string(f"Closed ssh({self.username})")

    def check_connected(self):
        try:
            if self.client is not None:
                transport = self.client.get_transport()
                if transport is not None:
                    output = transport.is_active()
                    self.ConnectedState = output
                else:
                    output = False
                    self.ConnectedState = False
            else:
                output = False
                self.ConnectedState = False
            return output
        except Exception as exc:
            self.ConnectedState = False
            return False

    def send_command(self, command, sudo=False, inputs=None,time_out=None):
        if inputs is None:
            inputs = []
        command = 'sudo -S ' + command if sudo else command
        stdin, stdout, stderr = self.client.exec_command(command,timeout=time_out)
        if sudo:
            stdin.write(self.userpass + '\n')
            stdin.flush()
        for i in inputs:
            stdin.write(i + '\n')
            stdin.flush()
            time.sleep(0.5)
        output = stdout.read().decode('utf-8', errors='ignore')
        errors = stderr.read().decode('utf-8', errors='ignore')
        if self.client.get_transport().is_active():
            if not sudo:
                out_string = output + '\n' + errors
            else:
                out_string = output if output != '' else errors
            return out_string
        else:
            return 'Connection lost' + '\n'

    def connect_sftp(self, host=None,port=None, jump_flag=None, jump_host=None, jump_port=None, jump_user=None,
                jump_pass=None, user=None, secret=None):
        self.username = user if user is not None else self.username
        self.userpass = secret if user is not None else self.userpass
        self.host = host if host is not None else self.host
        self.port = port if port is not None else self.port
        self.jump_flg = jump_flag if jump_flag is not None else self.jump_flg
        self.jump_host = jump_host if jump_host is not None else self.jump_host
        self.jump_port = jump_port if jump_port is not None else self.jump_port
        self.jump_user = jump_user if jump_user is not None else self.jump_user
        self.jump_pass = jump_pass if jump_pass is not None else self.jump_pass
        self.send_log_string(f"Opening sFTP")
        if self.jump_flg:
            self.send_log_string(f"Connecting via jump host {self.jump_host}")
            self.send_log_string(f"[Local]--->ssh--->")
            try:
                self.jump_client.connect(hostname=self.jump_host, username=self.jump_user, password=self.jump_pass, port=self.jump_port,
                                       timeout=10)
            except Exception as exc:
                self.send_log_string(f"Can't connect to Jump host. {exc}")
            else:
                self.send_log_string(f"[Local]--->ssh--->{self.jump_host}--->", True)
                try:
                    self.jump_hostTransport = self.jump_client.get_transport()
                    self.jump_hostChannel = self.jump_hostTransport.open_channel("direct-tcpip", (self.host, self.port),
                                                                                 (self.jump_host, self.port), timeout=10)
                except Exception as exc:
                    self.send_log_string(f"Can't create channel to host. {exc}")
                else:
                    self.send_log_string(f"[Local]--->ssh--->{self.jump_host}--->tunnel--->", True)
                    try:
                        self.sftpTransport = paramiko.Transport(sock=self.jump_hostChannel)
                        self.sftpTransport.connect(username=self.username, password=self.userpass)
                        self.sftpClient = paramiko.SFTPClient.from_transport(self.sftpTransport)
                    except Exception as exc:
                        self.send_log_string(f"Can't connect via jump host. {exc}")
                    else:
                        self.send_log_string(f"[Local]--->ssh--->{self.jump_host}--->tunnel--->sftp--->[device]",True)
        else:
            self.sftpTransport = paramiko.Transport((self.host, self.port))
            self.sftpTransport.connect(username=self.username, password=self.userpass)
            self.sftpClient = paramiko.SFTPClient.from_transport(self.sftpTransport)

    def send_sftp(self, file_name,dest_dir=None):
        head, tail = os.path.split(file_name)
        self.file_tail = tail
        if dest_dir == None:
            dest_dir = f'/home/{self.username}/'
        try:
            self.load_progress = 0
            self.direction = "Sending"
            self.sftpClient.put(localpath=file_name, remotepath=f'{dest_dir}{tail}', callback=self.status_transmit_sftp)
            self.send_log_string(f"Sending {tail} file ... 100%",True)
        except Exception as exc:
            self.send_log_string(f"No send...Problem {exc}")
        else:
            self.send_log_string(f"File {tail} transmitted OK")
            return 1

    def receive_sftp(self, file_name,dest_dir=None):
        head, tail = os.path.split(file_name)
        self.file_tail = tail
        if dest_dir == None:
            dest_dir = f'./'
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        try:
            self.load_progress = 0
            self.direction = 'Receiving'
            self.sftpClient.get(remotepath=file_name,localpath=f'{dest_dir}{tail}', callback=self.status_transmit_sftp)
            self.send_log_string(f"Receiving {tail} file ... 100%", True)
        except Exception as exc:
            self.send_log_string(f"No receive...Problem {exc}")
        else:
            self.send_log_string(f"File {tail} received OK")
            return 1

    def status_transmit_sftp(self,current,total):
        proc = current*100//total
        if proc != self.load_progress:
            self.send_log_string(f"{self.direction} {self.file_tail} file ... {current*100//total}%", True)
            self.load_progress = proc

    def close_sftp(self):
        if self.check_connected():
            if self.jump_flg:
                self.jump_client.close()
            self.sftpTransport.close()
            self.send_log_string(f"Closed sFTP", False)

    def add_task(self, task_name):
        """Метод вызывается из GUI-потока для добавления задачи в очередь"""
        self.task_queue.put(task_name)

    def stop(self):
        """Метод для полной остановки потока при дисконнекте"""
        self.is_running = False
        self.task_queue.put("EXIT")  # Толкаем поток, чтобы он вышел из ожидания .get()

    def run_loop(self):
        """Бесконечный цикл обработки команд в QThread"""

        self.buttons_state_signal.emit('connecting')
        self.connect()
        if not self.check_connected():
            self.stop()
        else:
            self.get_device_info()
            self.get_device_settings()
            self.buttons_state_signal.emit('connected')
        # ГЛАВНЫЙ ЦИКЛ ПОТОКА
        while self.is_running:
            try:
                # Поток блокируется (спит) здесь, пока в очереди ничего нет.
                # timeout нужен, чтобы поток мог периодически проверять флаг self.is_running
                task = self.task_queue.get(timeout=1.0)

                if task == "EXIT":
                    break

                # Обработка команд
                self.execute_command(task)

                # Сообщаем очереди, что задача успешно обработана
                self.task_queue.task_done()

            except queue.Empty:
                # Сюда заходим раз в секунду, если очередь пуста. Просто идем на новый круг.
                continue

        # Выход из цикла — закрываем сессию
        try:
            self.close_sftp()
        except:
            ...
        try:
            self.close()
        except:
            ...
        self.buttons_state_signal.emit('disconnected')
        self.finished_signal.emit()

    def send_log_string(self,text,change_last_line = False):
        self.log_signal.emit(text,change_last_line)

    def execute_command(self, task):
        """Здесь выполняются команды. Пока метод не завершится,
        следующая задача из очереди не возьмется!"""

        if task == "read_settings":
            self.get_device_settings()

        elif task == "update_start":
            self.send_log_string("Update start.")

        elif task == "update_finish":
            self.send_log_string("Update finish. Reboot is needed")

        elif task == "restart_service":
            self.send_log_string("Service is restarting...")
            self.send_command('systemctl restart synapse-device',True)
            self.add_task("status_service")

        elif task == "stop_service":
            self.send_log_string("Service is stoping...")
            self.send_command('systemctl stop synapse-device',True)
            self.add_task("status_service")

        elif task == "status_service":
            status = self.send_command('systemctl status synapse-device | grep "Active:"',True).strip()
            self.send_log_string(status)

        elif task == "reboot_device":
            self.send_log_string(f"Checking FS before reboot. Please wait")
            self.send_command("rm /home/ubuntu/partition_extended", False)
            self.send_command("mount -o remount,ro /", True)
            self.send_command("fsck -y /dev/mmcblk0p2", True)
            self.send_log_string(f"Rebooting")
            self.send_command("reboot", True)
            self.add_task("EXIT")

        elif task == "update_netplan":
            self.update_netplan()

        elif task == "update_chrony":
            self.update_chrony()

        elif task == "update_device_config":
            self.update_device_config()

        elif task == "repair_partition":
            self.send_log_string(f"Start repair root partition.")
            self.send_command(f"rm /home/ubuntu/partition_extended")
            cmd = f"bash -c 'mount -o remount,ro / ; e2fsck -f -y /dev/mmcblk0p2 ; mount -o remount,rw /'"
            self.send_command(cmd, True)
            cmd = f"bash -c 'growpart /dev/mmcblk0 2 -v -u off ; partx -u /dev/mmcblk0 ; resize2fs /dev/mmcblk0p2'"
            self.send_command(cmd, True)
            self.send_log_string(f"Finish repair root partition.")

    def update_netplan(self):
        self.send_log_string(f"Changing netplan.")
        netplan_lst = self.send_command("ls /etc/netplan", True).splitlines()
        netplan_lst = [i for i in netplan_lst if i.endswith('.yaml')]
        if self.main_settings['ServersIpMask1'] != '' and self.main_settings['ServerIpAddrA1'] != '':
            srv_bin_mask1 = [int(i) for i in self.main_settings['ServersIpMask1'].split('.')]
            srv_net_address1 = [int(i) for i in self.main_settings['ServerIpAddrA1'].split('.')]
            srv_net_address1 = list(map(lambda x, y: x & y, srv_bin_mask1, srv_net_address1))
            srv_sum_mask1 = sum(bin(int(i)).count('1') for i in self.main_settings['ServersIpMask1'].split('.'))
            srv_net_address1 = f'{".".join(map(str, srv_net_address1))}/{srv_sum_mask1}'
        else:
            srv_net_address1 = '0.0.0.0/0'
        if self.main_settings['ServersIpMask2'] != '' and self.main_settings['ServerIpAddrA2'] != '':
            srv_bin_mask2 = [int(i) for i in self.main_settings['ServersIpMask2'].split('.')]
            srv_net_address2 = [int(i) for i in self.main_settings['ServerIpAddrA2'].split('.')]
            srv_net_address2 = list(map(lambda x, y: x & y, srv_bin_mask2, srv_net_address2))
            srv_sum_mask2 = sum(bin(int(i)).count('1') for i in self.main_settings['ServersIpMask2'].split('.'))
            srv_net_address2 = f'{".".join(map(str, srv_net_address2))}/{srv_sum_mask2}'
        else:
            srv_net_address2 = '0.0.0.0/0'
        mask1 = sum(bin(int(i)).count('1') for i in self.main_settings['DeviceIpMask1'].split('.'))
        mask2 = sum(bin(int(i)).count('1') for i in self.main_settings['DeviceIpMask2'].split('.'))
        if self.main_settings['DeviceIpAddr1'] != '':
            ip1_and_mask1 = str(f"{self.main_settings['DeviceIpAddr1']}/{mask1}")
        else:
            ip1_and_mask1 = ""
        if self.main_settings['DeviceIpAddr2'] != '':
            ip2_and_mask2 = str(f"{self.main_settings['DeviceIpAddr2']}/{mask2}")
        else:
            ip2_and_mask2 = ""
        for i in netplan_lst:
            filename = i
            dir = '/etc/netplan/'
            netplan = self.convert_from_yaml(self.send_command(f"cat /etc/netplan/{i}", True))
            aname = 'eth0'
            if aname in netplan['network']['ethernets'].keys():
                netplan['network']['ethernets'][aname]['optional'] = True
                if 'gateway4' in netplan['network']['ethernets'][aname]:
                    del netplan['network']['ethernets'][aname]['gateway4']
                if 'routes' in netplan['network']['ethernets'][aname]:
                    del netplan['network']['ethernets'][aname]['routes']
                if 'routing-policy' in netplan['network']['ethernets'][aname]:
                    del netplan['network']['ethernets'][aname]['routing-policy']
                netplan['network']['ethernets'][aname]['macaddress'] = self.main_settings['MacAddr1']
                netplan['network']['ethernets'][aname]['addresses'] = ip1_and_mask1.split()
                if self.main_settings['DHCP1'] == True and self.main_settings['DeviceIpAddr1'] == '':
                    del netplan['network']['ethernets'][aname]['addresses']
                netplan['network']['ethernets'][aname]['dhcp4'] = self.main_settings['DHCP1']
                if self.main_settings['DeviceIpGW1'] != "":
                    if self.main_settings['UseGW4']:
                        netplan['network']['ethernets'][aname]['gateway4'] = self.main_settings['DeviceIpGW1']
                    else:
                        new_gw = [{'to': srv_net_address1, 'via': self.main_settings['DeviceIpGW1']}]
                        netplan['network']['ethernets'][aname]['routes'] = new_gw
            aname = 'eth1'
            if aname in netplan['network']['ethernets'].keys():
                netplan['network']['ethernets'][aname]['optional'] = True
                if 'gateway4' in netplan['network']['ethernets'][aname]:
                    del netplan['network']['ethernets'][aname]['gateway4']
                if 'routes' in netplan['network']['ethernets'][aname]:
                    del netplan['network']['ethernets'][aname]['routes']
                if 'routing-policy' in netplan['network']['ethernets'][aname]:
                    del netplan['network']['ethernets'][aname]['routing-policy']
                netplan['network']['ethernets'][aname]['macaddress'] = self.main_settings['MacAddr2']
                netplan['network']['ethernets'][aname]['addresses'] = ip2_and_mask2.split()
                if self.main_settings['DHCP2'] == True and self.main_settings['DeviceIpAddr2'] == '':
                    del netplan['network']['ethernets'][aname]['addresses']
                netplan['network']['ethernets'][aname]['dhcp4'] = self.main_settings['DHCP2']
                if self.main_settings['DeviceIpGW2'] != "":
                    if self.main_settings['UseGW4']:
                        netplan['network']['ethernets'][aname]['gateway4'] = self.main_settings['DeviceIpGW2']
                    else:
                        new_gw = [{'to': srv_net_address2, 'via': self.main_settings['DeviceIpGW2']}]
                        netplan['network']['ethernets'][aname]['routes'] = new_gw
            new = self.convert_to_yaml(netplan)
            self.send_log_string(f"Writing {i}... ")
            self.send_command(f'mv {dir}{filename} {dir}{filename}.bak', True)
            self.file_to_device(new, filename, dir)
            self.send_log_string(f"Writing {i}... Done",True)

    def update_chrony(self):
        self.send_log_string(f"Changing time sync.")
        servers = [i for i in self.main_settings['TimeServers'] if i != '']
        chrony_dir = self.send_command("ls /etc/chrony", True).splitlines()
        filename = 'chrony.conf'
        dir = '/etc/chrony/'
        if filename in chrony_dir:
            chrony_file = self.send_command(f"cat {dir}{filename}", True).splitlines()
            new_list = list()
            for i in chrony_file:
                if i.startswith('server') or i.startswith('#Synapse'):
                    continue
                else:
                    new_list.append(i)
            chrony_file = new_list
            chrony_file.append("#Synapse")
            for i in servers:
                chrony_file.append(f'server {i}')
            new = '\n'.join(chrony_file)
            self.send_log_string(f"Writing {filename}... ")
            self.send_command(f'mv {dir}{filename} {dir}{filename}.bak', True)
            self.file_to_device(new, filename, dir)
            self.send_log_string(f"Writing {filename}... Done",True)
            self.send_log_string(f"Restarting timemaster.")
            self.send_command(f"systemctl restart timemaster", True)
            self.send_log_string(self.send_command(f"systemctl status timemaster | grep 'Active'",
                                                 False).strip())
        else:
            self.send_log_string(f"No chrony, changing timesyncd.")
            timesync_dir = self.send_command("ls /etc/systemd", True).splitlines()
            filename = 'timesyncd.conf'
            dir = '/etc/systemd/'
            if filename in timesync_dir:
                timesync_file = self.send_command(f"cat {dir}{filename}", True).splitlines()
                servers = ' '.join(servers)
                for i in timesync_file:
                    if i.startswith('NTP=') or i.startswith('#NTP='):
                        if servers == '':
                            timesync_file[timesync_file.index(i)] = f'#NTP='
                        else:
                            timesync_file[timesync_file.index(i)] = f'NTP={servers}'
                    elif i.startswith('FallbackNTP'):
                        timesync_file[timesync_file.index(i)] = '#FallbackNTP='
                new = '\n'.join(timesync_file)
                self.send_log_string(f"Writing {filename}... ")
                self.send_command(f'mv {dir}{filename} {dir}{filename}.bak', True)
                self.file_to_device(new, filename, dir)
                self.send_log_string(f"Writing {filename}... Done",True)
                self.send_log_string(f"Restarting timesyncd.")
                self.send_command(f"systemctl restart systemd-timesyncd", True)
                self.send_log_string(self.send_command(f"systemctl status systemd-timesyncd | grep 'Active'",
                                                     False).strip())

    def update_device_config(self):
        self.send_log_string(f"Changing synapse-device settings.")
        device_dir = self.send_command("ls /usr/share/synapse/device/storage", True).splitlines()
        dir = '/usr/share/synapse/device/storage/'
        filename = 'ConnectionInfo-ConnectionInfo0.json'
        if filename in device_dir:
            connection_info_file = self.convert_from_json(self.send_command(f"cat {dir}{filename}", True))
            connection_info_file['value']['self_ip_addr'] = self.main_settings['DeviceIpAddr1']
            connection_info_file['value']['self_ip_addr2'] = self.main_settings['DeviceIpAddr2']
            connection_info_file['value']['server_ip_addr'] = self.main_settings['ServerIpAddrA1']
            connection_info_file['value']['server_ip_addr2'] = self.main_settings['ServerIpAddrA2']
            connection_info_file['value']['server_b_ip_addr'] = self.main_settings['ServerIpAddrB1']
            connection_info_file['value']['server_b_ip_addr2'] = self.main_settings['ServerIpAddrB2']
            connection_info_file['value']['server_tcp_port'] = self.main_settings['ServerJsonPortA']
            connection_info_file['value']['server_b_tcp_port'] = self.main_settings['ServerJsonPortB']
            connection_info_file['value']['server_secure_tcp'] = self.main_settings['ServerSecureTCP']
            connection_info_file = self.convert_to_json(connection_info_file)
            self.send_log_string(f"Writing {filename}... ")
            self.file_to_device(connection_info_file, filename, dir)
            self.send_log_string(f"Writing {filename}... Done",True)
        filename = 'DeviceInfo-DeviceInfo.json'
        if filename in device_dir:
            connection_info_file = self.convert_from_json(self.send_command(f"cat {dir}{filename}", True))
            connection_info_file['value']['unique_unit_id'] = self.main_settings['DeviceID']
            if 'uart_path' in connection_info_file['value'].keys():
                connection_info_file['value']['uart_path'] = '/dev/ttyUL2' if self.main_settings['UartUL2'] else '/dev/ttyPS1'
            if 'device_version' in connection_info_file['value'].keys():
                if not 'HwFirmware' in connection_info_file['value']['device_version']:
                    connection_info_file['value']['device_version']['HwFirmware'] = ''
            connection_info_file = self.convert_to_json(connection_info_file)
            self.send_log_string(f"Writing {filename}... ")
            self.file_to_device(connection_info_file, filename, dir)
            self.send_log_string(f"Writing {filename}... Done",True)
        filename = 'DeviceData-DeviceData0.json'
        if filename in device_dir:
            connection_info_file = self.convert_from_json(self.send_command(f"cat {dir}{filename}", True))
            connection_info_file['value']['dect_active_control'] = self.main_settings['DectActiveControl']
            connection_info_file = self.convert_to_json(connection_info_file)
            self.send_log_string(f"Writing {filename}... ")
            self.file_to_device(connection_info_file, filename, dir)
            self.send_log_string(f"Writing {filename}... Done",True)
        filename = 'LocalAudioMetersData-LocalAudioMetersData.json'
        if filename in device_dir:
            connection_info_file = self.convert_from_json(self.send_command(f"cat {dir}{filename}", True))
            connection_info_file['value']['Enabled'] = self.main_settings['AMEnabled']
            connection_info_file['value']['Config']['SilenceAudioThreshold'] = self.main_settings['AMSilenceAudioThreshold']
            connection_info_file['value']['Config']['SilenceCountThreshold'] = self.main_settings['AMSilenceCountThreshold']
            connection_info_file = self.convert_to_json(connection_info_file)
            self.send_log_string(f"Writing {filename}... ")
            self.file_to_device(connection_info_file, filename, dir)
            self.send_log_string(f"Writing {filename}... Done",True)
        # Change hostname data
        dir = '/etc/'
        filename = 'hostname'
        self.send_log_string(f"Changing hostname.")
        cur_hostname = self.send_command(f"cat {dir}{filename}", True).replace('\n', '')
        self.send_log_string(f"Writing {filename}... ")
        self.file_to_device(self.main_settings['DeviceID'], filename, dir)
        self.send_log_string(f"Writing {filename}... Done",True)
        filename = 'hosts'
        cur_hosts = self.send_command(f"cat {dir}{filename}", True)
        self.send_log_string(f"Writing {filename}... ")
        new_hosts = cur_hosts.replace(cur_hostname, self.main_settings['DeviceID'])
        self.file_to_device(new_hosts, filename, dir)
        self.send_log_string(f"Writing {filename}... Done",True)

    def get_device_info(self):
        try:
            self.send_log_string(f"Device checking")
            self.send_command('touch cardtest')
            if 'cardtest' in self.send_command('ls').splitlines():
                self.send_log_string(f"SD-card is OK")
                self.send_command('rm cardtest')
            else:
                #QMessageBox.critical('SD card error', f'{self.EntryDeviceIP.text()}: SD card write error is detected')
                self.send_log_string(f"SD card write error is detected")
            self.netplan_checker()
            self.send_log_string(f"Getting device info. Please wait...")
            settings = self.convert_from_json(
                self.send_command('cat /usr/share/synapse/device/storage/DeviceInfo-DeviceInfo.json'))
            status = "ID: " + self.get_from_dict(settings['value'], 'unique_unit_id', '')
            self.send_log_string(status)
            if 'device_version' in settings['value'].keys():
                status = "Device version: " + self.get_from_dict(settings['value']['device_version'],
                                                                          'BuildVersion', '')
                self.send_log_string(status)
                status = "Boot version: " + self.get_from_dict(settings['value']['device_version'],
                                                                        'HwFirmware', '')
                self.send_log_string(status)
            if not 'sysrq-trigger' in self.send_command("ls /proc | grep sysrq-trigger").split('\n'):
                self.send_log_string(f"Sysrq status: no. Boot update is needed")
            else:
                self.send_log_string(f"Sysrq status: ok")
            size = self.send_command("lsblk | grep 'mmcblk0 '").strip().split(' ')
            size = ''.join([i for i in size if 'G' in i])
            status = f"SD-card capacity: {size}"
            self.send_log_string(status)
            root_part = self.send_command("df -h | grep '/dev/root '").strip().split(' ')
            root_part = [i for i in root_part if i != '']
            status = f"Root partition capacity: {root_part[1]} ({root_part[3]} free)"
            self.send_log_string(status)
            img_version = self.send_command("cat /home/ubuntu/img_version").strip().splitlines()
            img_version = ''.join([i for i in img_version if not i.startswith('cat: ')])
            status = f"Image version: {img_version}"
            self.send_log_string(status)
            status = self.send_command("service synapse-device status | grep 'Active'").strip()
            self.send_log_string(status)
            # if chk_state_autoread.get():
            #    btn_button_area_get_settings_clicked()
        except Exception as exc:
            self.send_log_string(f"Problem: {exc}")

    def get_from_dict(self, dictionary=None, dict_key='', default=''):
        if dictionary is None:
            dictionary = dict()
        result = dictionary.get(dict_key, default)
        if not dict_key in dictionary:
            #QMessageBox.warning('Bad configuration file', f'"{dict_key}" not found\n"Full update" is required')
            self.send_log_string(f'Missed {dict_key}. Full update is required')
        return result

    def netplan_checker(self):
        self.send_log_string("Checking netplan files.")
        ethernets = (('eth0', '10-eth0.yaml'), ('eth1', '20-eth1.yaml'))
        renderer = 'NetworkManager' if 'NetworkManager' in self.send_command('ls /usr/sbin/',
                                                                                True).splitlines() else 'networkd'
        netplan_lst = self.send_command("ls /etc/netplan", True).splitlines()
        netplan_lst = [i for i in netplan_lst if i.endswith('.yaml')]
        netplan_len = len(netplan_lst)
        if netplan_len == 2 and '10-eth0.yaml' in netplan_lst and '20-eth1.yaml' in netplan_lst:
            self.send_log_string("Netplan files are OK.")
        elif netplan_len == 0:
            self.send_log_string("No netplan files detected.")
            self.file_to_device(self.convert_to_yaml(self.generate_default_netplan(0, renderer)), '10-eth0.yaml', '/etc/netplan/')
            self.file_to_device(self.convert_to_yaml(self.generate_default_netplan(1, renderer)), '20-eth1.yaml', '/etc/netplan/')
            self.send_log_string("New netplan generated.")
        else:
            self.send_log_string(f"Repair netplan files.")
            try_convert = False
            if netplan_len > 2:
                if self.ask_user_dialog("Netplan problem",'Too much netplan files detected.\n'
                                                          'Press "Yes" to try repair.\n'
                                                          'Auto "No" in 30 seconds'):
                    try_convert = True
                    self.send_log_string("Trying to repair files.")
                else:
                    if self.ask_user_dialog("Netplan problem",'Make default netplan?.\n'
                                                          'Auto "No" in 30 seconds'):
                        for i in netplan_lst:
                            self.send_command(f'mv /etc/netplan/{i} /etc/netplan/{i}.bak', True)
                        self.file_to_device(self.convert_to_yaml(self.generate_default_netplan(0, renderer)), '10-eth0.yaml',
                                       '/etc/netplan/')
                        self.file_to_device(self.convert_to_yaml(self.generate_default_netplan(1, renderer)), '20-eth1.yaml',
                                       '/etc/netplan/')
                        self.send_log_string("New netplan generated.")
            if netplan_len < 3 or try_convert:
                for i in netplan_lst:
                    netplan_dict = self.convert_from_yaml( self.send_command(f"cat /etc/netplan/{i}", False))
                    for num in range(0, 2):
                        new_netplan = self.generate_default_netplan(num, renderer)
                        if ethernets[num][0] in netplan_dict['network']['ethernets']:
                            new_netplan['network']['ethernets'][ethernets[num][0]] = \
                            netplan_dict['network']['ethernets'][ethernets[num][0]]
                            self.send_command(f'mv /etc/netplan/{i} /etc/netplan/{i}.bak', True)
                            self.file_to_device(self.convert_to_yaml(new_netplan), ethernets[num][1], '/etc/netplan/')
            self.send_log_string("Done.")

    def generate_default_netplan(self, eth=0, renderer='networkd'):
        kor = (('eth0', '192.168.88.137/24', 'FA:CE:80:4A:00:00'), ('eth1', '192.168.188.137/24', 'FA:CE:80:4B:00:00'))
        default_netplan = {'network': {'ethernets': {
            kor[eth][0]: {'addresses': [kor[eth][1]], 'dhcp4': False, 'macaddress': kor[eth][2], 'optional': True}},
                                       'renderer': renderer,
                                       'version': 2}}
        return default_netplan

    def get_device_settings(self):
        self.send_log_string("Getting device settings. Please wait...",False)
        try:
            path = '/etc/netplan/'
            lst_files = [i for i in self.send_command(f"ls {path}").split('\n') if i[-5:] == '.yaml']
            for i in lst_files:
                cur_netplan_file = self.convert_from_yaml(self.send_command(f"cat {path}{i}"))
                aname = 'eth0'
                if aname in cur_netplan_file['network']['ethernets']:
                    if 'addresses' in cur_netplan_file['network']['ethernets'][aname]:
                        addr = str(cur_netplan_file['network']['ethernets'][aname]['addresses'])
                        addr = addr[addr.find("'") + 1:]
                        mask = addr[addr.find("/"):addr.find("'")]
                        addr = addr[:addr.find('/')]
                    else:
                        addr = ''
                        mask = '/24'
                    mac = str(cur_netplan_file['network']['ethernets'][aname]['macaddress'])
                    self.current_settings['DeviceIpAddr1'] = addr
                    self.current_settings['MacAddr1'] = mac
                    self.current_settings['DeviceIpMask1'] = mask
                    self.current_settings['DHCP1'] = bool(cur_netplan_file['network']['ethernets'][aname]['dhcp4'])
                    srv_mask1 = '/24'
                    if 'gateway4' in cur_netplan_file['network']['ethernets'][aname]:
                        gw = cur_netplan_file['network']['ethernets'][aname]['gateway4']
                    elif 'routes' in cur_netplan_file['network']['ethernets'][aname]:
                        gw = cur_netplan_file['network']['ethernets'][aname]['routes'][0]['via']
                        srv_mask1 = str(cur_netplan_file['network']['ethernets'][aname]['routes'][0]['to'])
                        if '0.0.0.0' in srv_mask1:
                            srv_mask1 = "/24"
                    else:
                        gw = ''
                    self.current_settings['DeviceIpGW1'] = gw
                    self.current_settings['ServersIpMask1'] = srv_mask1[srv_mask1.rfind("/"):]
                aname = 'eth1'
                if aname in cur_netplan_file['network']['ethernets']:
                    if 'addresses' in cur_netplan_file['network']['ethernets'][aname]:
                        addr = str(cur_netplan_file['network']['ethernets'][aname]['addresses'])
                        addr = addr[addr.find("'") + 1:]
                        mask = addr[addr.find("/"):addr.find("'")]
                        addr = addr[:addr.find('/')]
                    else:
                        addr = ''
                        mask = '/24'
                    mac = str(cur_netplan_file['network']['ethernets'][aname]['macaddress'])
                    self.current_settings['DeviceIpAddr2'] = addr
                    self.current_settings['MacAddr2'] = mac
                    self.current_settings['DeviceIpMask2'] = mask
                    self.current_settings['DHCP2'] = bool(cur_netplan_file['network']['ethernets'][aname]['dhcp4'])
                    srv_mask2 = '/24'
                    if 'gateway4' in cur_netplan_file['network']['ethernets'][aname]:
                        gw = cur_netplan_file['network']['ethernets'][aname]['gateway4']
                    elif 'routes' in cur_netplan_file['network']['ethernets'][aname]:
                        gw = cur_netplan_file['network']['ethernets'][aname]['routes'][0]['via']
                        srv_mask2 = str(cur_netplan_file['network']['ethernets'][aname]['routes'][0]['to'])
                        if '0.0.0.0' in srv_mask2:
                            srv_mask2 = "/24"
                    else:
                        gw = ''
                    self.current_settings['DeviceIpGW2'] = gw
                    self.current_settings['ServersIpMask2'] = srv_mask2[srv_mask2.rfind("/"):]
            path = '/usr/share/synapse/device/storage/'
            try:
                device_dir = self.send_command("ls /usr/share/synapse/device/storage", True).splitlines()
                filename = 'ConnectionInfo-ConnectionInfo0.json'
                if filename in device_dir:
                    cur_device_file = self.convert_from_json(self.send_command(f"cat {path}{filename}"))
                    self.current_settings['ServerIpAddrA1'] = self.get_from_dict(cur_device_file['value'], 'server_ip_addr', '')
                    self.current_settings['ServerIpAddrA2'] = self.get_from_dict(cur_device_file['value'], 'server_ip_addr2', '')
                    self.current_settings['ServerIpAddrB1'] = self.get_from_dict(cur_device_file['value'], 'server_b_ip_addr', '')
                    self.current_settings['ServerIpAddrB2'] = self.get_from_dict(cur_device_file['value'], 'server_b_ip_addr2',
                                                                       '')
                    self.current_settings['ServerJsonPortA'] = int(
                        self.get_from_dict(cur_device_file['value'], 'server_tcp_port', '15351'))
                    self.current_settings['ServerJsonPortB'] = int(
                        self.get_from_dict(cur_device_file['value'], 'server_b_tcp_port', '15351'))
                    self.current_settings['ServerSecureTCP'] = bool(
                        self.get_from_dict(cur_device_file['value'], 'server_secure_tcp', ''))
                filename = 'DeviceInfo-DeviceInfo.json'
                if filename in device_dir:
                    cur_device_file = self.convert_from_json(self.send_command(f"cat {path}{filename}"))
                    self.current_settings['DeviceID'] = self.get_from_dict(cur_device_file['value'], 'unique_unit_id', '')
                    self.current_settings['UartUL2'] = True if self.get_from_dict(cur_device_file['value'], 'uart_path',
                                                                        '') == '/dev/ttyUL2' else False
                filename = 'DeviceData-DeviceData0.json'
                if filename in device_dir:
                    cur_device_file = self.convert_from_json(self.send_command(f"cat {path}{filename}"))
                    self.current_settings['DectActiveControl'] = bool(
                        self.get_from_dict(cur_device_file['value'], 'dect_active_control', ''))
                filename = 'LocalAudioMetersData-LocalAudioMetersData.json'
                if filename in device_dir:
                    cur_device_file = self.convert_from_json(self.send_command(f"cat {path}{filename}"))
                    self.current_settings['AMEnabled'] = bool(self.get_from_dict(cur_device_file['value'], 'Enabled', ''))
                    self.current_settings['AMLevelOverflow'] = float(
                        self.get_from_dict(cur_device_file['value']['Config'], 'LevelOverflow', ''))
                    self.current_settings['AMNominalLevel'] = float(
                        self.get_from_dict(cur_device_file['value']['Config'], 'NominalLevel', ''))
                    self.current_settings['AMSilenceAudioThreshold'] = float(
                        self.get_from_dict(cur_device_file['value']['Config'], 'SilenceAudioThreshold', ''))
                    self.current_settings['AMSilenceCountThreshold'] = int(
                        self.get_from_dict(cur_device_file['value']['Config'], 'SilenceCountThreshold', ''))
            except Exception as exc:
                self.send_log_string(f"Something went wrong. {exc}")
            path = '/etc/chrony/chrony.conf'
            try:
                chrony_dir = self.send_command("ls /etc/chrony", True).splitlines()
                filename = 'chrony.conf'
                if filename in chrony_dir:
                    cur_device_file = self.send_command(f"cat {path}").split('\n')
                    self.current_settings['TimeServers'] = ','.join([i[7:] for i in cur_device_file if 'server' in i])
                else:
                    chrony_dir = self.send_command("ls /etc/systemd", True).splitlines()
                    filename = 'timesyncd.conf'
                    if filename in chrony_dir:
                        cur_device_file = self.send_command(f"cat /etc/systemd/timesyncd.conf").split('\n')
                        servers = []
                        for i in cur_device_file:
                            if 'NTP=' in i:
                                servers.extend(i[i.index('=') + 1:].strip().split(' '))
                        self.current_settings['TimeServers'] = ','.join(servers)
            except Exception as exc:
                self.send_log_string(f"Something went wrong. {exc}")
            self.update_entry.emit(self.current_settings)
        except Exception as exc:
            self.send_log_string(f"Something went wrong. {exc}")
        else:
            self.send_log_string(f"Device settings received")

    def convert_from_yaml(self, data):
        return yaml.safe_load(data)

    def convert_to_yaml(self, data):
        return yaml.dump(data, indent=2, default_flow_style=False)

    def convert_from_json(self, data):
        return json.loads(data)

    def convert_to_json(self, data):
        return json.dumps(data, indent=4, ensure_ascii=False)

    def file_to_device(self,data, filename, dir):
        data = data.replace("`", "\\`")
        data = data.replace("$", "\\$")
        data = data.replace('"', '\\"').splitlines()
        data = '\n'.join(data)
        lst = self.send_command(f'ls', True)
        if filename in lst:
            self.send_command(f'rm {filename}', True)
        cmd_1 = f'echo -e "{data}" > {filename}'
        cmd_2 = f'chown --reference={dir}{filename} {filename}'
        cmd_3 = f'chmod --reference={dir}{filename} {filename}'
        cmd_4 = f'mv {filename} {dir}{filename}'
        full_cmd = f"bash -c '{cmd_1} ; {cmd_2} ; {cmd_3} ; {cmd_4}'"
        self.send_command(full_cmd,True)
        #self.send_command(f'echo -e "{data}" > {filename}', True)
        #self.send_command(f'chown --reference={dir}{filename} {filename}', True)
        #self.send_command(f'chmod --reference={dir}{filename} {filename}', True)
        #self.send_command(f'mv {filename} {dir}{filename}', True)

    def ask_user_dialog(self,header,text):
        result_obj = DialogResult()
        # Блокируем поток и ждем ответа от главного интерфейса
        result_obj.mutex.lock()
        self.request_decision.emit(result_obj,header,text)
        # Фоновый поток засыпает, пока GUI не вызовет condition.wakeAll()
        result_obj.condition.wait(result_obj.mutex)
        # Читаем ответ, который записал GUI поток
        user_agreed = result_obj.value
        result_obj.mutex.unlock()
        return user_agreed

class SynapseDevice:
    def __init__(self):
        self.thread : QThread
        self.worker : InteractiveSSHWorker
        self.thread = None
        self.worker = None
        self.isTr804 = True
        self.update_filepath = ''

        self.init_ui()

    def init_ui(self):
        self.CentralWidget = central_widget

        self.MarginsContent = (1, 1, 1, 1)
        self.AllDisablableElements = []
        self.ValidateLineEdits = []

        main_layout = QVBoxLayout(self.CentralWidget)
        main_layout.setContentsMargins(*self.MarginsContent)
        main_layout.setSpacing(0)

        # ========================================== Frame Connection ==========================================
        self.connection_frame = QWidget()
        self.connection_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout_connection_frame = QVBoxLayout(self.connection_frame)
        layout_connection_frame.setContentsMargins(*self.MarginsContent)
        self.connection_tabs = QTabWidget()
        # Tab1
        connection_tab_1 = QWidget()
        layout_connection_tab_1 = QGridLayout(connection_tab_1)
        # layout_connection_tab_1.setSpacing(0)
        layout_connection_tab_1.setContentsMargins(*self.MarginsContent)
        layout_connection_tab_1.setColumnStretch(0, 0)
        layout_connection_tab_1.setColumnStretch(1, 0)
        layout_connection_tab_1.setColumnStretch(2, 0)
        layout_connection_tab_1.setColumnStretch(3, 0)

        self.EntryDeviceIP = self.create_qlineedit(False,False,"192.168.88.137", 'Enter IP-address')

        self.ButtonConnect = QPushButton("Connect")
        self.ButtonConnect.setCheckable(True)
        self.ButtonConnect.clicked.connect(self.connect_ssh)
        # self.ButtonConnect.setMinimumWidth(100)
        self.CheckBoxJH = QCheckBox("Enable Jumphost")
        self.CheckBoxJH.setChecked(False)

        layout_connection_tab_1.addWidget(QLabel('IP-address:'), 0, 0)
        layout_connection_tab_1.addWidget(self.EntryDeviceIP, 0, 1)
        layout_connection_tab_1.addWidget(self.CheckBoxJH, 0, 2)
        layout_connection_tab_1.addWidget(self.ButtonConnect, 1, 0, 1, 4)

        self.connection_tabs.addTab(connection_tab_1, "Connection")

        # Tab2
        connection_tab_2 = QWidget()
        layout_connection_tab_2 = QGridLayout(connection_tab_2)
        layout_connection_tab_2.setSpacing(2)
        layout_connection_tab_2.setContentsMargins(*self.MarginsContent)
        layout_connection_tab_2.setColumnStretch(0, 0)
        layout_connection_tab_2.setColumnStretch(1, 0)
        layout_connection_tab_2.setColumnStretch(2, 0)
        layout_connection_tab_2.setColumnStretch(3, 0)

        self.EntryDeviceUser = self.create_qlineedit(False,False,'ubuntu', 'Device username')
        self.EntryDevicePass = self.create_qlineedit(False,False,'temppwd', 'Device password', 60, True)
        self.EntryJHAddress = self.create_qlineedit(False,False,'192.168.88.10', 'JumpHost address')
        self.EntryJHPort = self.create_qlineedit(False,False,'22', 'JumpHost port')
        self.EntryJHPort.setValidator(QIntValidator(1, 65535))
        self.EntryJHUser = self.create_qlineedit(False,False,'synapse', 'JumpHost username')
        self.EntryJHPass = self.create_qlineedit(False,False,'synapse', 'JumpHost password', 60, True)

        current_row = 0

        layout_connection_tab_2.addWidget(QLabel('User:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_connection_tab_2.addWidget(self.EntryDeviceUser, current_row, 1)
        layout_connection_tab_2.addWidget(QLabel('JH IP:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_connection_tab_2.addWidget(self.EntryJHAddress, current_row, 3)
        layout_connection_tab_2.addWidget(QLabel('JH User:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_connection_tab_2.addWidget(self.EntryJHUser, current_row, 5)

        current_row += 1

        layout_connection_tab_2.addWidget(QLabel('Password:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_connection_tab_2.addWidget(self.EntryDevicePass, current_row, 1)
        layout_connection_tab_2.addWidget(QLabel('JH Port:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_connection_tab_2.addWidget(self.EntryJHPort, current_row, 3)
        layout_connection_tab_2.addWidget(QLabel('JH Password:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_connection_tab_2.addWidget(self.EntryJHPass, current_row, 5)

        self.connection_tabs.addTab(connection_tab_2, "Settings")
        layout_connection_frame.addWidget(self.connection_tabs)

        # ========================================== Frame Settings ==========================================
        self.settings_frame = QWidget()
        self.settings_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout_settings_frame = QVBoxLayout(self.settings_frame)
        layout_settings_frame.setContentsMargins(0, 0, 0, 0)
        layout_settings_frame.setSpacing(0)
        # layout_settings_frame.setSpacing(0)
        layout_settings_frame.setContentsMargins(*self.MarginsContent)
        self.settings_tabs = QTabWidget()

        # Tab 1 - Parameters
        settings_tab_1 = QWidget()
        layout_settings_tab_1 = QGridLayout(settings_tab_1)
        layout_settings_tab_1.setContentsMargins(0, 0, 0, 0)
        layout_settings_tab_1.setSpacing(2)

        self.EntryDeviceIP1 = self.create_qlineedit(True,True,'192.168.88.137', 'IP-addr1 or set DHCP1')
        self.EntryDeviceIP2 = self.create_qlineedit(True,True,'192.168.188.137', 'IP-addr2 or set DHCP2')
        self.EntryDeviceMAC1 = self.create_qlineedit(True,True,'FA:CE:80:4A:00:00', 'Device MAC-address 1')
        self.EntryDeviceMAC2 = self.create_qlineedit(True,True,'FA:CE:80:4B:00:00', 'Device MAC-address 2')
        self.EntryDeviceMask1 = self.create_qlineedit(True,True,'255.255.255.0', 'xxx.xxx.xxx.xxx or xx')
        self.EntryDeviceMask2 = self.create_qlineedit(True,True,'255.255.255.0', 'xxx.xxx.xxx.xxx or xx')
        self.EntryDeviceID = self.create_qlineedit(True,True,'TR8040000', 'TR8040000')
        self.EntryDeviceID.setMaxLength(16)
        self.EntryServerAIP1 = self.create_qlineedit(True,True,'192.168.88.10', 'Server A IP-address 1')
        self.EntryServerAIP2 = self.create_qlineedit(True,True,'192.168.188.10', 'Server A IP-address 2')
        self.EntryServerBIP1 = self.create_qlineedit(True,True,'192.168.88.11', 'Server B IP-address 1')
        self.EntryServerBIP2 = self.create_qlineedit(True,True,'192.168.188.11', 'Server B IP-address 2')
        self.EntryServerMask1 = self.create_qlineedit(True,True,'255.255.255.0', 'xxx.xxx.xxx.xxx or xx')
        self.EntryServerMask2 = self.create_qlineedit(True,True,'255.255.255.0', 'xxx.xxx.xxx.xxx or xx')
        self.ButtonReadDevice = QPushButton("Read device")
        self.ButtonDefaultSettings = QPushButton("Default settings")
        self.ButtonFullUpdate1 = QPushButton("Update")

        self.ButtonFullUpdate1.clicked.connect(self.update_device)
        self.ButtonReadDevice.clicked.connect(self.read_device)
        self.ButtonDefaultSettings.clicked.connect(self.default_settings)
        self.EntryDeviceIP1.editingFinished.connect(lambda: self.ip_validation(self.EntryDeviceIP1))
        self.EntryDeviceIP2.editingFinished.connect(lambda: self.ip_validation(self.EntryDeviceIP2))
        self.EntryServerAIP1.editingFinished.connect(lambda: self.ip_validation(self.EntryServerAIP1))
        self.EntryServerAIP2.editingFinished.connect(lambda: self.ip_validation(self.EntryServerAIP2))
        self.EntryServerBIP1.editingFinished.connect(lambda: self.ip_validation(self.EntryServerBIP1))
        self.EntryServerBIP1.editingFinished.connect(lambda: self.ip_validation(self.EntryServerBIP1))
        self.EntryDeviceMask1.editingFinished.connect(lambda: self.mask_validation(self.EntryDeviceMask1))
        self.EntryDeviceMask2.editingFinished.connect(lambda: self.mask_validation(self.EntryDeviceMask2))
        self.EntryServerMask1.editingFinished.connect(lambda: self.mask_validation(self.EntryServerMask1))
        self.EntryServerMask2.editingFinished.connect(lambda: self.mask_validation(self.EntryServerMask2))
        self.EntryDeviceMAC1.editingFinished.connect(lambda: self.mac_validation(self.EntryDeviceMAC1))
        self.EntryDeviceMAC2.editingFinished.connect(lambda: self.mac_validation(self.EntryDeviceMAC2))

        current_row = 0

        layout_settings_tab_1.addWidget(QLabel('Device ID:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryDeviceID, current_row, 1)
        layout_settings_tab_1.addWidget(self.ButtonReadDevice, current_row, 2, 1, 2)
        layout_settings_tab_1.addWidget(self.ButtonDefaultSettings, current_row, 4, 1, 2)

        current_row += 1

        layout_settings_tab_1.addWidget(QLabel('Device IP1:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryDeviceIP1, current_row, 1)
        layout_settings_tab_1.addWidget(QLabel('Device Mask1:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryDeviceMask1, current_row, 3)
        layout_settings_tab_1.addWidget(QLabel('Device MAC1:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryDeviceMAC1, current_row, 5)

        current_row += 1

        layout_settings_tab_1.addWidget(QLabel('Device IP2:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryDeviceIP2, current_row, 1)
        layout_settings_tab_1.addWidget(QLabel('Device Mask2:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryDeviceMask2, current_row, 3)
        layout_settings_tab_1.addWidget(QLabel('Device MAC2:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryDeviceMAC2, current_row, 5)

        current_row += 1

        layout_settings_tab_1.addWidget(QLabel('ServerA IP1:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryServerAIP1, current_row, 1)
        layout_settings_tab_1.addWidget(QLabel('ServerB IP1:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryServerBIP1, current_row, 3)
        layout_settings_tab_1.addWidget(QLabel('SrvMask IP1:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryServerMask1, current_row, 5)

        current_row += 1

        layout_settings_tab_1.addWidget(QLabel('ServerA IP2:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryServerAIP2, current_row, 1)
        layout_settings_tab_1.addWidget(QLabel('ServerB IP2:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryServerBIP2, current_row, 3)
        layout_settings_tab_1.addWidget(QLabel('SrvMask IP2:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_1.addWidget(self.EntryServerMask2, current_row, 5)

        current_row += 1

        layout_settings_tab_1.addWidget(self.ButtonFullUpdate1,current_row,0,1,6)

        self.settings_tabs.addTab(settings_tab_1, "Main")
        layout_settings_frame.addWidget(self.settings_tabs)

        # Tab 2 - Additional
        settings_tab_2 = QWidget()
        layout_settings_tab_2 = QGridLayout(settings_tab_2)
        layout_settings_tab_2.setContentsMargins(0, 0, 0, 2)
        layout_settings_tab_2.setSpacing(2)
        for i in (1,3,5):
            layout_settings_tab_2.setColumnStretch(i, 1)

        self.EntryDeviceGW1 = self.create_qlineedit(True,True,'', 'Gateway 1 IP-address')
        self.EntryDeviceGW2 = self.create_qlineedit(True,True,'', 'Gateway 2 IP-address')
        self.EntryServerAPort = self.create_qlineedit(True,True,'15351', 'Server A port')
        self.EntryServerBPort = self.create_qlineedit(True,True,'15351', 'Server B port')
        self.CheckBoxDHCP1 = self.create_qcheckbox('LAN1')
        self.CheckBoxDHCP2 = self.create_qcheckbox('LAN2')
        self.CheckBoxGateWay4 = self.create_qcheckbox()
        self.CheckBoxSecureTCP = self.create_qcheckbox()
        self.CheckBoxTimeServers = self.create_qcheckbox('Timeservers:')
        self.CheckBoxSilenceDetector = self.create_qcheckbox()
        self.CheckBoxUseUL2 = self.create_qcheckbox()
        self.CheckBoxDectOff = self.create_qcheckbox()
        self.SpinBoxSilenceDetector = QDoubleSpinBox()
        self.SpinBoxSilenceDetector.setRange(-90.0, 0.0)
        self.SpinBoxSilenceDetector.setSingleStep(0.1)
        self.EntrySilenceTime = self.create_qlineedit(False,True,'3000', 'Detection time, ms')
        self.EntrySilenceTime.setValidator(QIntValidator(0, 300000))
        self.EntryTimeServers = self.create_qlineedit(False,False,'', 'xxx.xxx.xxx.xxx,yyy.yyy.yyy.yyy')
        self.EntryTimeServers.setEnabled(False)
        self.ButtonFullUpdate2 = QPushButton("Update")

        self.ButtonFullUpdate2.clicked.connect(self.update_device)
        self.CheckBoxDHCP1.toggled.connect(lambda: self.EntryDeviceIP1.editingFinished.emit())
        self.CheckBoxDHCP2.toggled.connect(lambda: self.EntryDeviceIP2.editingFinished.emit())
        self.CheckBoxTimeServers.toggled.connect(self.EntryTimeServers.setEnabled)
        self.EntryServerAPort.editingFinished.connect(lambda: self.port_validation(self.EntryServerAPort))
        self.EntryServerBPort.editingFinished.connect(lambda: self.port_validation(self.EntryServerBPort))
        self.EntryDeviceGW1.editingFinished.connect(lambda: self.ip_validation(self.EntryDeviceGW1))
        self.EntryDeviceGW2.editingFinished.connect(lambda: self.ip_validation(self.EntryDeviceGW2))

        current_row = 0
        layout_settings_tab_2.setRowStretch(0, 1)
        current_row +=1

        layout_settings_tab_2.addWidget(QLabel('ServerA port:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.EntryServerAPort, current_row, 1)
        layout_settings_tab_2.addWidget(QLabel('Secure TCP:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.CheckBoxSecureTCP, current_row, 3, Qt.AlignmentFlag.AlignCenter)
        layout_settings_tab_2.addWidget(QLabel('DHCP:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.CheckBoxDHCP1, current_row, 5, Qt.AlignmentFlag.AlignLeft)
        layout_settings_tab_2.addWidget(self.CheckBoxDHCP2, current_row, 5, Qt.AlignmentFlag.AlignRight)

        current_row += 1

        layout_settings_tab_2.addWidget(QLabel('ServerB port:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.EntryServerBPort, current_row, 1)
        layout_settings_tab_2.addWidget(QLabel('Use ttyUL2:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.CheckBoxUseUL2, current_row, 3, Qt.AlignmentFlag.AlignCenter)
        layout_settings_tab_2.addWidget(QLabel('Silence detector:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.CheckBoxSilenceDetector, current_row, 5, Qt.AlignmentFlag.AlignCenter)

        current_row += 1

        layout_settings_tab_2.addWidget(QLabel('Gateway IP1:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.EntryDeviceGW1, current_row, 1)
        layout_settings_tab_2.addWidget(QLabel('Auto DECT off:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.CheckBoxDectOff, current_row, 3, Qt.AlignmentFlag.AlignCenter)
        layout_settings_tab_2.addWidget(QLabel('Silence level, dB:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.SpinBoxSilenceDetector, current_row, 5)

        current_row += 1

        layout_settings_tab_2.addWidget(QLabel('Gateway IP2:'), current_row, 0, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.EntryDeviceGW2, current_row, 1)
        layout_settings_tab_2.addWidget(QLabel('Gateway4:'), current_row, 2, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.CheckBoxGateWay4, current_row, 3, Qt.AlignmentFlag.AlignCenter)
        layout_settings_tab_2.addWidget(QLabel('Silence time, ms:'), current_row, 4, Qt.AlignmentFlag.AlignRight)
        layout_settings_tab_2.addWidget(self.EntrySilenceTime, current_row, 5)

        current_row += 1

        layout_settings_tab_2.addWidget(self.CheckBoxTimeServers, current_row, 0)
        layout_settings_tab_2.addWidget(self.EntryTimeServers, current_row, 1, 1, 5)

        current_row += 1

        layout_settings_tab_2.addWidget(self.ButtonFullUpdate2, current_row, 0, 1, 6)

        self.settings_tabs.addTab(settings_tab_2, "Additional")

        # Tab 3 - controls
        controls_tab_3 = QTabWidget()
        layout_controls_tab_3 = QGridLayout(controls_tab_3)
        layout_controls_tab_3.setContentsMargins(*self.MarginsContent)
        layout_controls_tab_3.setSpacing(2)

        self.ButtonRestart = QPushButton('Restart service')
        self.ButtonStop = QPushButton('Stop service')
        self.ButtonStatus = QPushButton('Status service')
        self.ButtonReboot = QPushButton('Reboot device')
        self.ButtonRepairPartition = QPushButton('Repair partition')
        self.ComboBoxDeviceMode = QComboBox()
        self.ComboBoxDeviceMode.addItems(['Synapse device','AES67 Node'])
        self.ComboBoxDeviceMode.setEditable(False)

        self.ButtonRestart.clicked.connect(lambda: self.send_command('restart_service'))
        self.ButtonStop.clicked.connect(lambda: self.send_command('stop_service'))
        self.ButtonStatus.clicked.connect(lambda: self.send_command('status_service'))
        self.ButtonReboot.clicked.connect(lambda: self.send_command('reboot_device'))
        self.ButtonRepairPartition.clicked.connect(lambda: self.send_command('repair_partition'))

        current_row = 0

        layout_controls_tab_3.addWidget(QLabel('Device mode: '), current_row,0,Qt.AlignmentFlag.AlignRight)
        layout_controls_tab_3.addWidget(self.ComboBoxDeviceMode,current_row,1)
        layout_controls_tab_3.addWidget(self.ButtonReboot, current_row, 2)

        current_row += 1

        layout_controls_tab_3.addWidget(self.ButtonRepairPartition, current_row, 2)

        current_row += 1

        layout_controls_tab_3.addWidget(self.ButtonRestart,current_row,0)
        layout_controls_tab_3.addWidget(self.ButtonStop, current_row, 1)
        layout_controls_tab_3.addWidget(self.ButtonStatus, current_row, 2)

        self.settings_tabs.addTab(controls_tab_3, "Controls")

        # Tab 4 - firmware
        controls_tab_4 = QTabWidget()
        layout_controls_tab_4 = QGridLayout(controls_tab_4)
        layout_controls_tab_4.setContentsMargins(*self.MarginsContent)
        layout_controls_tab_4.setSpacing(2)

        self.LabelFileName = QLabel("Filename:")
        self.ButtonOpenFile = QPushButton('Open file')

        self.ButtonOpenFile.clicked.connect(self.open_file)

        current_row = 0

        #layout_controls_tab_4.addWidget(QLabel("Filename: "), current_row, 0,Qt.AlignmentFlag.AlignLeft)
        layout_controls_tab_4.addWidget(self.LabelFileName, current_row, 0, 1, 6,Qt.AlignmentFlag.AlignLeft)

        current_row += 1

        layout_controls_tab_4.addWidget(self.ButtonOpenFile, current_row, 0,1,2)

        self.settings_tabs.addTab(controls_tab_4, "Firmware")

        # ========================================== Frame Log ==========================================
        self.log_frame = QWidget()
        layout_log_frame = QVBoxLayout(self.log_frame)
        # layout_log_frame.setSpacing(0)
        layout_log_frame.setContentsMargins(*self.MarginsContent)
        self.TxtArea = QTextEdit()
        self.TxtArea.setReadOnly(True)
        self.TxtArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout_log_frame.addWidget(self.TxtArea)

        main_layout.addWidget(self.connection_frame, 1)
        main_layout.addWidget(self.settings_frame, 1)
        main_layout.addWidget(self.log_frame, 1)

        self.change_elements_state(False)

    def open_file(self):
        if self.isTr804:
            boot_filter = 'TR804BOOT*.tar'
            hex_filter = 'TR804*.hex'
            img_filter = 'TR804*p2.img.xz'
        else:
            boot_filter = 'TR807BOOT*.tar'
            hex_filter = 'TR807*.hex'
            img_filter = 'TR807*p2.img.xz'
        filters = f"(synapse-device*.deb dect_bs_arm*.bin dect_fp_fpga*.bin {hex_filter} {boot_filter} {img_filter})"
        self.update_filepath = self.select_file(self.CentralWidget,"Open file","",filters)
        if self.update_filepath:
            self.LabelFileName.setText(f"Filename: {os.path.basename(self.update_filepath)}")
        else:
            self.LabelFileName.setText("Filename:")

    def send_command(self,command):
        if self.thread is not None:
            if self.worker is not None:
                self.worker.add_task(command)
        else:
            self.update_txt_area('Not connected')

    def default_settings(self):
        if self.thread is not None:
            if self.worker is not None:
                self.dict_to_entry(self.worker.default_settings)
        else:
            self.update_txt_area('Not connected')

    def update_device(self):
        if self.thread is not None:
            if self.worker is not None:
                self.entry_to_dict(self.worker.main_settings)
                self.worker.add_task('update_start')
                self.worker.add_task('update_netplan')
                self.worker.add_task('update_chrony')
                self.worker.add_task('update_device_config')
                self.worker.add_task('update_finish')
        else:
            self.update_txt_area('Not connected')

    def read_device(self):
        if self.thread is not None:
            if self.worker is not None:
                self.worker.add_task("read_settings")
        else:
            self.update_txt_area('Not connected')

    def connect_ssh(self):
        if self.thread is None:
            self.thread = QThread()
            self.worker = InteractiveSSHWorker(self.EntryDeviceIP.text(),22,self.CheckBoxJH.isChecked(),
                                               self.EntryJHAddress.text(),self.EntryJHPort.text(),self.EntryJHUser.text(),
                                               self.EntryJHPass.text(),self.EntryDeviceUser.text(),self.EntryDevicePass.text())
            self.worker.moveToThread(self.thread)

            self.thread.started.connect(self.worker.run_loop)
            self.worker.log_signal.connect(self.update_txt_area)
            self.worker.buttons_state_signal.connect(self.update_buttons_state)
            self.worker.request_decision.connect(self.show_confirmation_dialog)
            self.worker.update_entry.connect(self.dict_to_entry)

            self.worker.finished_signal.connect(self.thread.quit)
            self.thread.finished.connect(self.on_disconnected)
            self.thread.finished.connect(self.thread.deleteLater)

            self.thread.start()
        else:
            self.worker.stop()

    def on_disconnected(self):
        self.worker = None
        self.thread = None

    def mac_validation(self,line_edit : QLineEdit):
        is_error = False
        mask = '0123456789ABCDEF:'
        address = line_edit.text()
        address = address.replace(';', ':')
        lst_mac = [i for i in address if i in mask]
        address = ''.join(lst_mac)
        new_mac = address
        if address == "":
            is_error = True
        else:
            lst_mac = [i for i in address.split(':') if i != '']
            if len(lst_mac) != 6:
                is_error = True
            for i in lst_mac:
                if int(i, 16) not in range(0, 256):
                    is_error = True
            new_mac = ':'.join([format(int(i, 16), '02X') for i in lst_mac])
        line_edit.setProperty("error", is_error)
        line_edit.setText(new_mac)
        self.update_entry_background(line_edit)

    def ip_validation(self, line_edit : QLineEdit):
        is_error = False
        mask = '0123456789.'
        address = line_edit.text()
        address = address.replace(',', '.')
        lst = [i for i in address if i in mask]
        address = ''.join(lst)
        new_ip = address
        if address != "":
            parts = [i for i in address.split('.') if i != '']
            if len(parts) != 4:
                is_error = True
            else:
                if any(not (0 <= int(p) < 255) for p in parts):
                    is_error = True
                new_ip = '.'.join(map(str, parts))
        else:
            is_dhcp_1 = (line_edit is self.EntryDeviceIP1 and self.CheckBoxDHCP1.isChecked())
            is_dhcp_2 = (line_edit is self.EntryDeviceIP2 and self.CheckBoxDHCP2.isChecked())
            is_gw1 = line_edit is self.EntryDeviceGW1
            is_gw2 = line_edit is self.EntryDeviceGW2
            if not (is_dhcp_1 or is_dhcp_2 or is_gw1 or is_gw2):
                is_error = True
        line_edit.setProperty("error", is_error)
        line_edit.setText(new_ip)
        self.update_entry_background(line_edit)

    def mask_validation(self, line_edit : QLineEdit):
        is_error = False
        mask = '0123456789.'
        mask2 = '0123456789'
        address = line_edit.text()
        address = address.replace(',', '.')
        if len(address) < 3:
            parts = [i for i in address if i in mask2]
        else:
            parts = [i for i in address if i in mask]
        address = ''.join(parts)
        if address == "":
            address = "24"
        if len(address) < 3:
            cidr = int(address)
            if 0 <= cidr <= 32:
                binary_str = '1' * cidr + '0' * (32 - cidr)
                parts = [str(int(binary_str[i:i + 8], 2)) for i in range(0, 32, 8)]
                address = '.'.join(parts)
            else:
                is_error = True
        parts = [p for p in address.split('.') if p != '']
        if len(parts) != 4:
            is_error = True
        else:
            if any(not (0 <= int(p) <= 255) for p in parts):
                is_error = True
            else:
                binary_mask = ''.join(format(int(p), '08b') for p in parts)
                if '01' in binary_mask:
                    is_error = True
        line_edit.setProperty("error", is_error)
        new_mask = '.'.join(map(str, parts))
        line_edit.setText(new_mask)
        self.update_entry_background(line_edit)

    def port_validation(self, line_edit : QLineEdit):
        is_error = False
        mask = '0123456789'
        port = line_edit.text()
        lst = [i for i in port if i in mask]
        port = ''.join(lst)
        if port == '':
            port = '22'
        if not (0 < int(port) <= 65535):
            is_error = True
        line_edit.setProperty("error", is_error)
        line_edit.setText(port)
        self.update_entry_background(line_edit)

    def devid_validation(self, line_edit : QLineEdit):
        is_error = False
        devid = line_edit.text()
        devid = devid[:16]
        line_edit.setProperty("error", is_error)
        line_edit.setText(devid)
        self.update_entry_background(line_edit)

    def update_entry_background(self,line_edit : QLineEdit):
        palette = line_edit.palette()
        if line_edit.property("error"):
            palette.setColor(QPalette.ColorGroup.Normal, QPalette.ColorRole.Base, QColor("#ff8080"))
        else:
            palette.setColor(QPalette.ColorGroup.Normal, QPalette.ColorRole.Base, QColor("white"))
        line_edit.setPalette(palette)
        if any(e.property("error") for e in self.ValidateLineEdits):
            self.update_buttons_state('lock_update')
        else:
            self.update_buttons_state('unlock_update')

    def update_buttons_state(self,state):
        if state == 'connecting':
            self.ButtonConnect.setChecked(True)
            self.ButtonConnect.setText('Connecting...')
            self.change_elements_state(False)
        elif state == 'connected':
            self.ButtonConnect.setChecked(True)
            self.ButtonConnect.setText('Disconnect')
            self.change_elements_state(True)
        elif state == 'disconnected':
            self.ButtonConnect.setChecked(False)
            self.ButtonConnect.setText('Connect')
            self.change_elements_state(False)
        elif state == 'lock_update':
            self.ButtonFullUpdate1.setEnabled(False)
            self.ButtonFullUpdate2.setEnabled(False)
        elif state == 'unlock_update':
            self.ButtonFullUpdate1.setEnabled(True)
            self.ButtonFullUpdate2.setEnabled(True)

    def change_elements_state(self,new_state : bool):
        for i in self.AllDisablableElements:
            i.setEnabled(new_state)

    def select_file(self, parent, title="Выберите файл", start_dir="", filters="Все файлы (*)"):
        file_path, _ = QFileDialog.getOpenFileName(
            parent, title, start_dir, filters
        )
        return file_path

    def show_confirmation_dialog(self, result_obj: DialogResult,header: str, text: str):
        # Создаем QMessageBox по правилам PyQt6
        msg_box = QMessageBox(self.CentralWidget)
        msg_box.setWindowTitle(header)
        msg_box.setText(text)

        # В PyQt6 используется QMessageBox.StandardButton
        yes_button = msg_box.addButton(QMessageBox.StandardButton.Yes)
        no_button = msg_box.addButton(QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        # Таймер на 30 секунд для автозакрытия окна
        timer = QTimer(msg_box)
        timer.setSingleShot(True)
        timer.timeout.connect(msg_box.close)
        timer.start(30000)  # 30 000 миллисекунд

        # exec() в PyQt6 пишется БЕЗ нижнего подчеркивания (в отличие от PyQt5)
        msg_box.exec()
        timer.stop()

        user_choice = msg_box.clickedButton() == yes_button

        # Безопасно передаем результат обратно в Worker и будим его
        result_obj.mutex.lock()
        result_obj.value = user_choice
        result_obj.condition.wakeAll()
        result_obj.mutex.unlock()

    def update_qlineedit(self,line_edit: QLineEdit,text=None):
        if text is not None:
            line_edit.setText(str(text))
        line_edit.editingFinished.emit()

    def entry_to_dict(self,dictionary):
        dictionary['DeviceIpAddr1'] = self.EntryDeviceIP1.text()
        dictionary['DeviceIpAddr2'] = self.EntryDeviceIP2.text()
        dictionary['MacAddr1'] = self.EntryDeviceMAC1.text()
        dictionary['MacAddr2'] = self.EntryDeviceMAC2.text()
        dictionary['DeviceIpMask1'] = self.EntryDeviceMask1.text()
        dictionary['DeviceIpMask2'] = self.EntryDeviceMask1.text()
        dictionary['ServerIpAddrA1'] = self.EntryServerAIP1.text()
        dictionary['ServerIpAddrA2'] = self.EntryServerAIP2.text()
        dictionary['ServerIpAddrB1'] = self.EntryServerBIP1.text()
        dictionary['ServerIpAddrB2'] = self.EntryServerBIP2.text()
        dictionary['ServersIpMask1'] = self.EntryServerMask1.text()
        dictionary['ServersIpMask2'] = self.EntryServerMask2.text()
        dictionary['ServerJsonPortA'] = int(self.EntryServerAPort.text())
        dictionary['ServerJsonPortB'] = int(self.EntryServerBPort.text())
        dictionary['DeviceID'] = self.EntryDeviceID.text()
        dictionary['ServerSecureTCP'] = self.CheckBoxSecureTCP.isChecked()
        dictionary['DHCP1'] = self.CheckBoxDHCP1.isChecked()
        dictionary['DHCP2'] = self.CheckBoxDHCP2.isChecked()
        dictionary['DeviceIpGW1'] = self.EntryDeviceGW1.text()
        dictionary['DeviceIpGW2'] = self.EntryDeviceGW2.text()
        dictionary['UartUL2'] = self.CheckBoxUseUL2.isChecked()
        dictionary['DectActiveControl'] = self.CheckBoxDectOff.isChecked()
        dictionary['AMEnabled'] = self.CheckBoxSilenceDetector.isChecked()
        dictionary['AMSilenceAudioThreshold'] = self.SpinBoxSilenceDetector.value()
        dictionary['AMSilenceCountThreshold'] = int(self.EntrySilenceTime.text())
        dictionary['UseGW4'] = self.CheckBoxGateWay4.isChecked()
        if self.CheckBoxTimeServers.isChecked():
            dictionary['TimeServers'] = self.CheckBoxTimeServers.text().split(',')
        else:
            dictionary['TimeServers'] = [dictionary['ServerIpAddrA1'], dictionary['ServerIpAddrA2'],
                                            dictionary['ServerIpAddrB1'], dictionary['ServerIpAddrB2']]

    def dict_to_entry(self,dictionary):
        self.update_qlineedit(self.EntryDeviceMAC1, dictionary['MacAddr1'])
        self.update_qlineedit(self.EntryDeviceMAC2, dictionary['MacAddr2'])
        self.update_qlineedit(self.EntryDeviceIP1, dictionary['DeviceIpAddr1'])
        self.update_qlineedit(self.EntryDeviceIP2, dictionary['DeviceIpAddr2'])
        self.update_qlineedit(self.EntryServerAIP1, dictionary['ServerIpAddrA1'])
        self.update_qlineedit(self.EntryServerAIP2, dictionary['ServerIpAddrA2'])
        self.update_qlineedit(self.EntryServerBIP1, dictionary['ServerIpAddrB1'])
        self.update_qlineedit(self.EntryServerBIP2, dictionary['ServerIpAddrB2'])
        self.update_qlineedit(self.EntryDeviceMask1,dictionary['DeviceIpMask1'])
        self.update_qlineedit(self.EntryDeviceMask2, dictionary['DeviceIpMask2'])
        self.update_qlineedit(self.EntryServerMask1,dictionary['ServersIpMask1'])
        self.update_qlineedit(self.EntryServerMask2, dictionary['ServersIpMask2'])
        self.update_qlineedit(self.EntryServerAPort, dictionary['ServerJsonPortA'])
        self.update_qlineedit(self.EntryServerBPort, dictionary['ServerJsonPortB'])
        self.update_qlineedit(self.EntryDeviceGW1, dictionary['DeviceIpGW1'])
        self.update_qlineedit(self.EntryDeviceGW2, dictionary['DeviceIpGW2'])
        self.update_qlineedit(self.EntryDeviceID, dictionary['DeviceID'])
        self.update_qlineedit(self.EntrySilenceTime, dictionary['AMSilenceCountThreshold'])
        self.update_qlineedit(self.EntryTimeServers, dictionary['TimeServers'])
        self.SpinBoxSilenceDetector.setValue(dictionary['AMSilenceAudioThreshold'])
        self.CheckBoxSilenceDetector.setChecked(dictionary['AMEnabled'])
        self.CheckBoxDectOff.setChecked(dictionary['DectActiveControl'])
        self.CheckBoxSecureTCP.setChecked(dictionary['ServerSecureTCP'])
        self.CheckBoxUseUL2.setChecked(dictionary['UartUL2'])
        self.CheckBoxDHCP1.setChecked(dictionary['DHCP1'])
        self.CheckBoxDHCP2.setChecked(dictionary['DHCP2'])

    def update_txt_area(self, text='', change_last_line=False):
        formatted_text = f'[{time.strftime("%H:%M:%S")}] {text}'
        cursor = self.TxtArea.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if change_last_line:
            cursor.movePosition(cursor.MoveOperation.StartOfBlock, cursor.MoveMode.KeepAnchor)
            cursor.insertText(formatted_text)
        else:
            self.TxtArea.append(formatted_text)
        self.TxtArea.ensureCursorVisible()

    def create_qlineedit(self,need_validation : bool,need_disable : bool, text='', place_holder='', min_width=60, password_mode=False) -> QLineEdit:
        new_entry = QLineEdit()
        new_entry.setProperty("error",False)
        if password_mode:
            new_entry.setEchoMode(QLineEdit.EchoMode.Password)
        new_entry.setText(text)
        new_entry.setPlaceholderText(place_holder)
        new_entry.setMinimumWidth(min_width)
        if need_disable:
            self.AllDisablableElements.append(new_entry)
        if need_validation:
            self.ValidateLineEdits.append(new_entry)
        return new_entry

    def create_qcheckbox(self, text='', chk_state=False, ) -> QCheckBox:
        new_chk = QCheckBox(text)
        new_chk.setChecked(chk_state)
        return new_chk

if __name__ == "__main__":
    app = QApplication(sys.argv)
    #app.font()
    app.setStyle('Fusion')

    window = QMainWindow()
    window.setWindowTitle("TR-804 configurator 26.08.2026")
    # self.resize(550, 600)
    # self.setMinimumSize(450, 500)

    # Шрифт по умолчанию
    app_font = QFont("Tahoma", 11)
    window.setFont(app_font)

    # Центральный виджет и главный layout
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    NewDevice = SynapseDevice()
    window.show()

    sys.exit(app.exec())