import logging
import re
import time
from socket import socket, AF_INET6, SOCK_DGRAM
from typing import Optional

import httpx


class CurrentIP:
    """
    获取局域网的出口IP，即本机在公网上的IP地址

    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
                2023-10-17 speedtest的api变动，遂强校验ip格式，并使用备用api
                2022-08-22 ip138的api已限流，即使10分钟请求一次，10次后仍被ban，寻找新的api
                2022-07-30 添加获取IPv6功能
                2022-07-26 代码重构，拆分出此类
    :author: Resurrection2981
                2025-05-07 共用公网 ip 出现查询结果来回变动时，多数api是错的导致计数方法失效，增加每个接口的权重，以及每个接口隔3秒取5次，大于等于3次一致次才纳入统计
                2025-05-06 fetch 增加全部接口取一次，返回出现最多的IP，避免部分地区共用公网 ip 出现查询结果来回变动
    :since: 2022-07-26
    """

    # re.compile会缓存编译后的正则
    # '0'开头也会被匹配，如：02.2.2.026
    _VALID_V4_EXP = re.compile(r'^((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}$')
    _FIND_V4_EXP = re.compile(r'((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}')
    # ::只能作为最后一个分隔符，不能作为第一个分隔符
    _VALID_V6_EXP = re.compile(r'^(([0-9A-Fa-f]{1,4}:){1,6})(:|[0-9A-Fa-f]{1,4}:)([0-9A-Fa-f]{1,4})$')

    def __init__(self, http_client: httpx.Client) -> None:
        """

        :param httpx.Client http_client: 完成基础配置的 http client
        """
        self._http_client = http_client
        self._logger = logging.getLogger(self.__class__.__name__)

    def fetch(self):
        """
        获取当前公网IP

        :return: '-1' if failed
        :rtype: str
        """
        sources = [
            # cip.cc (权重1) 似乎很久才刷新一次
            ("http://cip.cc", 1, lambda: self._FIND_V4_EXP.search(self._http_client.get('http://cip.cc').text).group()),
            # ipplus360 (权重1) 似乎很久才刷新一次
            ("https://www.ipplus360.com/getIP", 1, lambda: self._http_client.get('https://www.ipplus360.com/getIP').json().get('data')),
            # ip.sb (权重2)
            ("https://api-ipv4.ip.sb/ip", 2, lambda: self._http_client.get('https://api-ipv4.ip.sb/ip').text.strip()),
            # api迭代更新较快 (权重1)
            ("https://tisu-api-v3.speedtest.cn/speedUp/query", 1, lambda: self._http_client.get('https://tisu-api-v3.speedtest.cn/speedUp/query').json().get('data').get('addr').split(':')[0]),
            # 中科大测速网
            ("http://test.ustc.edu.cn/backend/getIP.php", 1, lambda: self._http_client.get('http://test.ustc.edu.cn/backend/getIP.php').json().get('processedString')),
            # 南京大学测速网#
            ("http://test.nju.edu.cn/backend/getIP.php", 1, lambda: self._http_client.get('http://test.nju.edu.cn/backend/getIP.php').json().get('processedString')) #,

            # 国内api: https://ip.skk.moe/ 但可能获取到的是ipv6
            # 清华大学测速网: https://iptv.tsinghua.edu.cn/st/getIP.php 但可能获取到的是ipv6
            # 两个未前后端分离，ip嵌在html中的网站
            # https://ip.tool.chinaz.com/
            # https://tool.lu/ip/

            # 美国备用 myip.com),
            # ("https://api.myip.com", 1, lambda: self._http_client.get('https://api.myip.com').json().get('ip')),
            # 美国备用 ipify.org))
            # ("https://api.ipify.org?format=json", 1, lambda: self._http_client.get('https://api.ipify.org?format=json').json().get('ip'))
        ]
        counts = {}
        for url, weight, src in sources:
            try:
                ip_counter = {}
                for i in range(5):
                    ip_try = src()
                    self._logger.info(f"Fetched IP from {url} (attempt {i+1}): {ip_try}")
                    time.sleep(3)
                    ip_counter[ip_try] = ip_counter.get(ip_try, 0) + 1

                # 选出现次数最多的 ip
                best_ip, best_count = max(ip_counter.items(), key=lambda x: x[1])
                # 出现次数 >= 3，且合法才计入
                if best_count >= 3 and isinstance(best_ip, str) and self.valid_v4(best_ip):
                    counts[best_ip] = counts.get(best_ip, 0) + weight
            except Exception as e:
                self._logger.exception(e)

        if not counts:
            return '-1'
        result_ip, max_count = max(counts.items(), key=lambda x: x[1])
        if max_count < 2:
            return '-1'
        return result_ip

    def fetch_v6(self, count=0):
        """
        获取当前在公网的IPv6地址

        :since: 2022-07-30
        :rtype: str
        :return: '-1' if no ipv6 network is available
        """
        # 和之前获取IPv4的设计不同，这里是递归，成功后无法打印从哪个api获取到ip地址，但是失败能提示是哪个api发生了错误
        r = '-1'
        try:
            # 中科大api：http://test6.ustc.edu.cn        稳
            if count == 0:
                r = self._http_client.get('http://test6.ustc.edu.cn/backend/getIP.php')
                r = r.json().get('processedString')
            # https://www.ipify.org/                   调试过程中容易返回IPv4，实际使用没问题
            if count == 1:
                r = self._http_client.get('https://api64.ipify.org?format=json')
                r = r.json().get('ip')
            # 清华大学api：https://ipv6.tsinghua.edu.cn  调试过程中可能会无响应，实际使用没问题
            if count == 2:
                r = self._http_client.get('https://ipv6.tsinghua.edu.cn/ip.php')
                r = r.json().get('ip_addr')

            # 其余api
            # 东北大学：http://speed.neu6.edu.cn/  路径  /getIP.php

        except Exception as e:
            self._logger.exception(e)
        if type(r) != str or not self.valid_v6(r):
            self._logger.error(f'\terror code: count={count}')
            if count < 2:
                return self.fetch_v6(count=count + 1)
            else:
                return '-1'
        self._logger.info(f'\tcurrent host IPv6: {r}')
        return r

    def get_local_ipv6(self) -> str:
        """
        因为IPv6没有局域网NAT转换，地址公网可用，可以通过ifconfig等本地操作获取地址
        """
        ip = '-1'
        s = socket(AF_INET6, SOCK_DGRAM)
        try:
            # 未发送数据，也不用管是否ping通
            s.connect(("2400:3200::1", 53))
            ip = s.getsockname()[0]
        except Exception as e:
            self._logger.exception(e)
        s.close()
        return ip

    def get_router_ipv6_snmp(self, router_ip: str, community: str = 'public', 
                             port: int = 161, interface_index: Optional[int] = None,
                             snmp_version: int = 2, username: str = None,
                             auth_key: str = None, priv_key: str = None) -> str:
        """
        通过 SNMP 从路由器获取 WAN 口 IPv6 地址
        
        :param router_ip: 路由器 IP 地址
        :param community: SNMPv2c community string (默认 'public')
        :param port: SNMP 端口 (默认 161)
        :param interface_index: 网络接口索引 (可选)
        :param snmp_version: SNMP 版本 (2=v2c, 3=v3，默认 2)
        :param username: SNMPv3 用户名 (仅 v3)
        :param auth_key: SNMPv3 认证密钥 (可选)
        :param priv_key: SNMPv3 加密密钥 (可选)
        :return: IPv6 地址或 '-1'
        :since: 2025-10-03
        """
        try:
            from lib.snmp_client import SNMPClient
            
            snmp = SNMPClient(router_ip, community, port, 
                            snmp_version=snmp_version, username=username,
                            auth_key=auth_key, priv_key=priv_key)
            ipv6 = snmp.get_wan_ipv6(interface_index)
            
            if ipv6 != '-1':
                self._logger.info(f'\tRouter IPv6 via SNMP: {ipv6}')
            
            return ipv6
            
        except ImportError:
            self._logger.error('SNMP library not installed. Please install: pip install pysnmp')
            return '-1'
        except Exception as e:
            self._logger.exception(e)
            return '-1'

    def get_router_ip_ssh(self, router_ip: str, username: str, password: str,
                         port: int, command: str, ip_type: str = 'ipv4') -> str:
        """
        通过 SSH 从路由器获取 WAN 口 IP 地址
        
        :param router_ip: 路由器 IP 地址
        :param username: SSH 用户名
        :param password: SSH 密码
        :param port: SSH 端口
        :param command: 获取 IP 的命令
        :param ip_type: IP 类型, 'ipv4' 或 'ipv6'
        :return: IP 地址或 '-1'
        :since: 2025-10-03
        """
        try:
            from lib.get_wanip_ssh import SSHRouter
            
            ssh_router = SSHRouter(router_ip, username, password, port)
            ip = ssh_router.get_wan_ip(command, ip_type)
            
            if ip != '-1':
                self._logger.info(f'\tRouter {ip_type} via SSH: {ip}')
            
            return ip
            
        except ImportError:
            self._logger.error('SSH library (paramiko) not installed. Please install: pip install paramiko')
            return '-1'
        except Exception as e:
            self._logger.exception(e)
            return '-1'

    @staticmethod
    def valid_v4(ip: str) -> bool:
        return CurrentIP._VALID_V4_EXP.match(ip) is not None

    @staticmethod
    def valid_v6(ip: str) -> bool:
        return CurrentIP._VALID_V6_EXP.match(ip) is not None
