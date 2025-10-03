import re
import paramiko
import logging
from typing import Optional

_logger = logging.getLogger(__name__)

class SSHHandle:
    def __init__(self, ip, port, username, password, sn=''):
        self.sn = sn
        self.ip = ip
        self.port = int(port)
        self.username = username
        self.password = password

        self.ssh = paramiko.SSHClient()
        # ssh白名单
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # 连接ssh
    def connect(self, timeout=3):
        try:
            self.ssh.connect(hostname=self.ip, port=self.port, username=self.username, password=self.password,
                             timeout=timeout)
        except Exception as e:
            _logger.error(f"SSH连接失败 {self.ip}:{self.port} - {e}")
            raise e

    def ssh_exec_command(self, cmd, prefix=''):
        """
            Execute a command on the ssh connection.
        :param ssh_obj: SSH object.
        :param cmd: command to run.
        :param prefix: Prefix to be used for printing
        :return: stdout and stderr
        """
        try:
            _, stdout_obj, stderr_obj = self.ssh.exec_command(cmd, timeout=5)
            exit_status = stdout_obj.channel.recv_exit_status()
            if exit_status == 0:
                _logger.debug(prefix + "[+] Successful Command:  " + cmd)
            else:
                _logger.warning(prefix + "[*] Command:" + cmd + " Return Code:" + str(exit_status))

        except paramiko.SSHException as e:
            _logger.error(prefix + "[!] Problem occurred while running command: %s, Error: %s" % (cmd, e))
            raise e
        stdout = stdout_obj.read().decode('utf-8', 'ignore')
        _logger.debug(prefix + "[>] Get Stdout:          " + cmd + "\n" + stdout)

        return stdout

    # 关闭ssh
    def close(self):
        try:
            self.ssh.close()
        except:
            pass


class SSHRouter:
    """
    通过 SSH 从路由器获取 WAN 口 IP 地址
    
    :since: 2025-10-03
    """
    
    def __init__(self, ip: str, username: str, password: str, port: int = 22):
        """
        初始化 SSH 路由器客户端
        
        :param ip: 路由器 IP 地址
        :param username: SSH 用户名
        :param password: SSH 密码
        :param port: SSH 端口,默认 22
        """
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self._logger = logging.getLogger(self.__class__.__name__)
    
    def get_wan_ip(self, command: str, ip_type: str = 'ipv4') -> str:
        """
        通过 SSH 执行命令获取路由器 WAN 口 IP
        
        :param command: 获取 IP 的命令
        :param ip_type: IP 类型, 'ipv4' 或 'ipv6'
        :return: IP 地址字符串,失败返回 '-1'
        """
        ssh_handle = None
        try:
            ssh_handle = SSHHandle(ip=self.ip, username=self.username, 
                                  password=self.password, port=self.port)
            ssh_handle.connect(timeout=5)
            
            result = ssh_handle.ssh_exec_command(cmd=command)
            
            if not result or result.strip() == '':
                self._logger.warning(f'获取 {ip_type} 失败: 命令返回为空')
                return '-1'
            
            # 尝试从 JSON 格式中提取 IP (带引号)
            ip_match = re.findall(r'\"(.*?)\"', result)
            if ip_match:
                ip = ip_match[0]
            else:
                # 直接使用返回结果
                ip = result.strip()
            
            # 验证 IP 格式
            if ip_type == 'ipv4':
                # IPv4 格式验证
                ipv4_pattern = re.compile(r'^((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}$')
                if not ipv4_pattern.match(ip):
                    self._logger.warning(f'获取的 IPv4 格式无效: {ip}')
                    return '-1'
            elif ip_type == 'ipv6':
                # IPv6 格式验证
                ipv6_pattern = re.compile(r'^(([0-9A-Fa-f]{1,4}:){1,6})(:|[0-9A-Fa-f]{1,4}:)([0-9A-Fa-f]{1,4})$')
                if not ipv6_pattern.match(ip):
                    self._logger.warning(f'获取的 IPv6 格式无效: {ip}')
                    return '-1'
            
            # self._logger.info(f'通过 SSH 获取路由器 {ip_type}: {ip}')
            return ip
            
        except Exception as e:
            self._logger.exception(f'SSH 获取 {ip_type} 失败: {e}')
            return '-1'
        finally:
            if ssh_handle:
                ssh_handle.close()


def main():
    # 测试代码
    router = SSHRouter(ip='192.168.0.1', username='root', 
                      password='Ruijie.1602', port=54133)
    
    # 测试获取 IPv4
    ipv4_cmd = "dev_sta get -m ipinfo | jq .wan.ip"
    wanip_v4 = router.get_wan_ip(ipv4_cmd, 'ipv4')
    print('WAN IPv4:', wanip_v4)
    
    # 测试获取 IPv6
    ipv6_cmd = "dev_sta get -m ipinfo | jq .wan.ipv6"
    wanip_v6 = router.get_wan_ip(ipv6_cmd, 'ipv6')
    print('WAN IPv6:', wanip_v6)


if __name__ == '__main__':
    main()
