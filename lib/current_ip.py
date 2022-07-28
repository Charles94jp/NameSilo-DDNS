import logging

import httpx


class CurrentIP:
    """
    获取局域网的出口IP，即本机在公网上的IP地址

    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
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
        self.ip138_url = None
        try:
            r = self._http_client.get('https://www.ip138.com/')
            api = r.text.split('<iframe src=\"//')[1]
            api = api.split('/\"')[0]
            self.ip138_url = api
        except Exception as e:
            self._logger.exception(e)
            if self.ip138_url is not None:
                self._logger.info('__init__: 未正确获取ip138的api，将使用备用api')

    def fetch(self):
        """
        获取当前公网IP

        :return: '-1' if failed
        :rtype: str
        """
        ip = r = '-1'
        if not self.ip138_url:
            try:
                ip = self._get_current_ip_bk()
            except Exception as e:
                self._logger.error('fetch: \tapi error')
            return ip

        try:
            r = self._http_client.get('http://' + self.ip138_url)
        except Exception as e:
            self._logger.exception(e)
            try:
                r = self._http_client.get('https://' + self.ip138_url)
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
                ip = self._get_current_ip_bk()
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
