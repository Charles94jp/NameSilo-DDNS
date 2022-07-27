import logging
import copy

import httpx


class NameSiloClient:
    """
    NameSilo客户端，可以获取和推送域名信息，可以存储key，域名ip等信息

    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
                2022-07-26 代码重构，拆分出此类
    :since: 2022-07-26
    """
    _API_BASE_URL = 'https://www.namesilo.com'

    def __init__(self, http_client: httpx.Client, conf: dict) -> None:
        """

        :param httpx.Client http_client: 完成基础配置的 http client
        :param dict conf: 解析后的配置文件
        """
        self._http_client = copy.copy(http_client)
        self._http_client.base_url = self._API_BASE_URL
        self._logger = logging.getLogger('NameSilo_DDNS')

        self._api_key = conf['key']
        # 适配两种配置文件的写法
        self.original_domains = conf.get('domains')
        if self.original_domains is None:
            self.original_domains = conf['domain']
        self.domains = []
        is_list = (type(self.original_domains) == list)
        # 分离域名和前面的前缀。支持处理列表，或者字符串。如果是字符串，则for循环每次取一个字符
        for i in self.original_domains:
            tmp = i.split('.') if is_list else self.original_domains.split('.')
            domain = tmp[-2] + '.' + tmp[-1]
            tmp = tmp[0:len(tmp) - 2]
            host = '.'.join(tmp)
            self.domains.append({'domain': domain, 'host': host})
            if not is_list:
                break
        self.fetch_domains_info()

    def fetch_domains_info(self) -> None:
        """
        拉取域名信息到对象中
        """
        for domain in self.domains:
            try:
                url = f"/api/dnsListRecords?version=1&type=xml&key={self._api_key}&domain={domain['domain']}"
                r = self._http_client.get(url)
                if r.status_code == 200:
                    r = r.text.split('<resource_record>')
                    _domain = domain['domain'] if domain['host'] == '@' or \
                                                  domain['host'] == '' else domain['host'] + '.' + domain['domain']
                    for record in r:
                        if record.find(f'<host>{_domain}</host>') != -1:
                            r = record
                            break
                    r = r.split('</record_id>')
                    domain['record_id'] = r[0].split('<record_id>')[-1]
                    domain['domain_ip'] = r[1].split('<value>')[1].split('</value>')[0]
                    self._logger.info(
                        f"get_domain_ip: \t'{domain['host']}.{domain['domain']}' resolution ip: " + domain['domain_ip'])
                else:
                    self._logger.error('get_domain_ip: \tError, process stopped. '
                                       'It could be due to the configuration file error, or the NameSilo server error.')
                    exit(-1)
            except httpx.ConnectError as e:
                self._logger.exception(e)
                self._logger.error('get_domain_ip: \tError, process stopped. '
                                   'It could be due to the configuration file error, or the NameSilo server error.')

    def update_domain_ip(self, new_ip: str):
        """
        推送新ip到NameSilo

        :param new_ip: 新的ip
        :return: 0 if successful, else the inverse of the number of failures
        """
        success1 = 10000
        error2 = 20000
        error3 = 30000
        for domain in self.domains:
            if domain['domain_ip'] == new_ip:
                continue
            try:
                _host = '' if domain["host"] == '@' else domain["host"]
                url = f"/api/dnsUpdateRecord?version=1&type=xml&rrttl=7207&key={self._api_key}" \
                      f"&domain={domain['domain']}&rrid={domain['record_id']}&rrhost={_host}&rrvalue={new_ip}"
                r = self._http_client.get(url)
                r = r1 = r.text
                r = r.split('<code>')[1]
                r = r.split('</code>')[0]
                if r == '300':
                    domain['domain_ip'] = new_ip
                    self._logger.info(f"update_domain_ip: \tupdate '{domain['host']}.{domain['domain']}' "
                                      f"completed: {domain['domain_ip']}")
                    success1 = success1 + 1
                elif r == '280':
                    self._logger.info(f'update_domain_ip: record_id has expired, re-query domain name information')
                    # 更新rrid，修复更新时api返回280：record_id missing or invalid
                    self.fetch_domains_info()
                    result = self.update_domain_ip(new_ip)
                    return result
                else:
                    error2 = error2 + 1
                    self._logger.error(f"update_domain_ip: \tupdate '{domain['host']}.{domain['domain']}' failed. "
                                       f"Namesilo response:\n{r1}")
            except Exception as e:
                error3 = error3 + 1
                self._logger.exception(e)
                self._logger.error(f"update_domain_ip: \tupdate '{domain['host']}.{domain['domain']}' error")
        if success1 > 10000:
            return 0
        if error2 > 20000:
            return -(error2 - 20000)
        if error3 > 30000:
            return -(error3 - 30000)

    def ip_equal(self, ip: str):
        """
        比对ip和所有域名的解析值是否相同

        :param str ip: 要比较的ip
        :rtype: bool
        :return: True or False
        """
        result = True
        for domain in self.domains:
            result = result & (ip == domain['domain_ip'])
        return result
