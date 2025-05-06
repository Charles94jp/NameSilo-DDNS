import logging
import re
from socket import socket, AF_INET6, SOCK_DGRAM

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
        sources = [
            lambda: self._http_client.get('https://www.ipplus360.com/getIP').json().get('data'),
            lambda: self._http_client.get('https://tisu-api-v3.speedtest.cn/speedUp/query').json().get('data').get('addr').split(':')[0],
            lambda: self._FIND_V4_EXP.search(self._http_client.get('http://cip.cc').text).group(),
            lambda: self._http_client.get('https://api-ipv4.ip.sb/ip').text.strip(),
            lambda: self._http_client.get('http://test.ustc.edu.cn/backend/getIP.php').json().get('processedString'),
            lambda: self._http_client.get('http://test.nju.edu.cn/backend/getIP.php').json().get('processedString'),
            lambda: self._http_client.get('https://api.myip.com').json().get('ip'),
            lambda: self._http_client.get('https://api.ipify.org?format=json').json().get('ip')
        ]
        counts = {}
        for src in sources:
            try:
                ip = src()
                if isinstance(ip, str) and self.valid_v4(ip):
                    counts[ip] = counts.get(ip, 0) + 1
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

    @staticmethod
    def valid_v4(ip: str) -> bool:
        return CurrentIP._VALID_V4_EXP.match(ip) is not None

    @staticmethod
    def valid_v6(ip: str) -> bool:
        return CurrentIP._VALID_V6_EXP.match(ip) is not None
