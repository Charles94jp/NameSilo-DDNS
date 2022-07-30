import logging

import httpx


class CurrentIP:
    """
    获取局域网的出口IP，即本机在公网上的IP地址

    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
                2022-07-30 添加获取IPv6功能
                2022-07-26 代码重构，拆分出此类
    :since: 2022-07-26
    """

    # 两个美国的备用api
    _MYIP_API = 'https://api.myip.com'
    _IPIFY_API = 'https://api.ipify.org?format=json'

    def __init__(self, http_client: httpx.Client) -> None:
        """

        :param httpx.Client http_client: 完成基础配置的 http client
        """
        self._http_client = http_client
        self._logger = logging.getLogger('NameSilo_DDNS')
        self._ip138_url = None
        try:
            r = self._http_client.get('https://www.ip138.com/')
            api = r.text.split('<iframe src=\"//')[1]
            api = api.split('/\"')[0]
            self._ip138_url = api
        except Exception as e:
            self._logger.exception(e)
            if self._ip138_url is not None:
                self._logger.info('__init__: \tThe api for ip138 is not correctly obtained, '
                                  'the alternate api will be used')

    def fetch(self):
        """
        获取当前公网IP

        :return: '-1' if failed
        :rtype: str
        """
        ip = '-1'
        if not self._ip138_url:
            try:
                ip = self._fetch_current_ip_bk()
            except Exception as e:
                self._logger.exception(e)
                self._logger.error('fetch: \tapi error')
            return ip

        try:
            r = self._http_client.get('http://' + self._ip138_url)
        except Exception as e:
            self._logger.exception(e)
            try:
                r = self._http_client.get('https://' + self._ip138_url)
            except Exception as e:
                self._logger.exception(e)
                return '-1'

        if r.status_code == 200:
            r = r.text
            r = r.split('您的IP地址是：')[1]
            ip = r.split('</title>')[0]
            self._logger.info(f'fetch: \tcurrent host ip(ip138): {ip}')
        else:
            try:
                ip = self._fetch_current_ip_bk()
            except Exception as e:
                self._logger.exception(e)
                self._logger.error('fetch: \tapi error')
        return ip

    def _fetch_current_ip_bk(self):
        """
        备用

        :return: '-1' if failed
        :rtype: str
        """
        ip = r = '-1'
        try:
            r = self._http_client.get(self._MYIP_API)
            r = r.json()
            ip = r['ip']
            self._logger.info(f'_fetch_current_ip_bk: \tcurrent host ip(myip): {ip}')
            return ip
        except Exception as e:
            self._logger.exception(e)
            r = self._http_client.get(self._IPIFY_API)
            r = r.json()
            ip = r['ip']
            self._logger.info(f'_fetch_current_ip_bk: \tcurrent host ip(ipify): {ip}')
            return ip

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
        if type(r) != str or r.find(':') == -1:
            self._logger.error(f'fetch_v6: \terror code: count={count}')
            if count < 2:
                return self.fetch_v6(count=count + 1)
            else:
                return '-1'
        self._logger.info(f'fetch_v6: \tcurrent host IPv6: {r}')
        return r
