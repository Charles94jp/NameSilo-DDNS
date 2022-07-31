import logging
import copy
import sys

import httpx


class NameSiloClient:
    """
    NameSilo客户端，可以获取和推送域名信息，可以存储key，域名ip等信息

    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
                2022-07-28 域名信息导出html table用于发邮件
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
        self._list_dns_api_cache = {}

        self._api_key = conf['key']
        # 适配两种配置文件的写法
        original_domains = conf.get('domains')
        if original_domains is None:
            original_domains = conf['domain']
        self.domains = []
        self.domains_ipv6 = []
        is_list = (type(original_domains) == list)
        # 分离域名和前面的前缀。支持处理列表，或者字符串。如果是字符串，则for循环每次取一个字符
        for i in original_domains:
            self.domains.append(NameSiloClient._separate(i if is_list else original_domains))
            if not is_list:
                break
        for i in conf.get('domains_ipv6', []):
            self.domains_ipv6.append(NameSiloClient._separate(i))
        pass

    @staticmethod
    def _separate(domain_name: str) -> dict:
        """
        分离出前缀host和域名本体domain，支持多级域名

        :param str domain_name: 完整域名 'aa.bb.cc'
        :rtype: dict
        :return: {'domain': 'bb.cc', 'host': 'aa'}
        """
        tmp = domain_name.split('.')
        domain = tmp[-2] + '.' + tmp[-1]
        tmp = tmp[0:len(tmp) - 2]
        host = '.'.join(tmp)
        return {'host': host, 'domain': domain}

    def fetch_domains_info(self) -> None:
        """
        拉取域名信息到对象中
        不提取_list_dns_api()，直接循环（self.domains+self.domains_ipv6）应该也可以
        """
        for domain in self.domains:
            self._list_dns_api(domain)
        for domain in self.domains_ipv6:
            self._list_dns_api(domain, clear=True)
        pass

    def _list_dns_api(self, domain: dict, clear=False) -> None:
        """

        :param domain: 直接对字典进行读取和修改操作，无返回值
        :param clear: 函数的最后清理缓存
        """
        try:
            r = self._list_dns_api_cache.get(domain['domain'])
            if r is None:
                url = f"/api/dnsListRecords?version=1&type=xml&key={self._api_key}&domain={domain['domain']}"
                r = self._http_client.get(url)
                self._list_dns_api_cache[domain['domain']] = r.text
                if r.status_code != 200:
                    self._logger.error('_list_dns_api: \tError, process stopped. It could be due to the '
                                       'configuration file error, or the NameSilo server error.')
                    sys.exit(-1)
                r = r.text
            r = r.split('<resource_record>')
            _domain = domain['domain'] if domain['host'] == '@' or \
                                          domain['host'] == '' else f"{domain['host']}.{domain['domain']}"
            for record in r:
                if record.find(f'<host>{_domain}</host>') != -1:
                    r = record
                    break
            r = r.split('</record_id>')
            domain['record_id'] = r[0].split('<record_id>')[-1]
            domain['domain_ip'] = r[1].split('<value>')[1].split('</value>')[0]
            self._logger.info(
                f"fetch_domains_info: \t'{domain['host']}{'.' if domain['host'] else ''}{domain['domain']}' "
                f"resolution ip: {domain['domain_ip']}")
        except httpx.ConnectError as e:
            self._logger.exception(e)
            self._logger.error('_list_dns_api: \tError, process stopped. '
                               'It could be due to the configuration file error, or the NameSilo server error.')
        if clear:
            self._list_dns_api_cache.clear()

    def update_domain_ip(self, new_ip: str, new_ipv6=None) -> int:
        """
        推送新ip到NameSilo

        :param new_ipv6:
        :param new_ip: 新的ip
        :rtype: int
        :return: 0 if successful, else the inverse of the number of failures
        """
        # 更新rrid，修复更新时api返回280：record_id missing or invalid
        self._logger.info('update_domain_ip: \tupdate record_id')
        self.fetch_domains_info()
        r1 = self._update_dns_api(self.domains, new_ip)
        if new_ipv6 is not None:
            r2 = self._update_dns_api(self.domains_ipv6, new_ipv6)
            # todo: 如果一正一负
            # todo: TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'
            return r1 + r2
        return r1

    def _update_dns_api(self, domains: list, new_ip) -> int:
        """
        可以是静态函数，但是需要logger和http client的配置

        :param domains:
        :param new_ip:
        :rtype: int
        :return: 0 if successful, else the inverse of the number of failures
        """
        success = 0
        fail = 0
        exception = 0
        for domain in domains:
            if domain['domain_ip'] == new_ip:
                continue
            full_domain = f"{domain['host']}{'.' if domain['host'] else ''}{domain['domain']}"
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
                    self._logger.info(f"update_dns_api: \tupdate '{full_domain}' "
                                      f"completed: {domain['domain_ip']}")
                    success = success + 1
                elif r == '280' and r1.find('must be a valid ipv') > -1:
                    self._logger.error(f'update_dns_api: ip type and domain type do not match\n{r1}')
                    fail = fail + 1
                else:
                    fail = fail + 1
                    self._logger.error(f"update_dns_api: \tupdate '{full_domain}' failed. "
                                       f"Namesilo response:\n{r1}")
            except Exception as e:
                exception = exception + 1
                self._logger.exception(e)
                self._logger.error(f"update_dns_api: \tupdate '{full_domain}' error")
        if success == len(domains):
            return 0
        if fail > 0:
            return -1 * fail
        if exception > 0:
            return -1 * exception

    def ip_equal(self, ip: str) -> bool:
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

    def ip_equal_ipv6(self, ip: str) -> bool:
        """
        比对ip和所有域名的解析值是否相同

        :param str ip: 要比较的ip
        :rtype: bool
        :return: True or False
        """
        result = True
        for domain in self.domains_ipv6:
            result = result & (ip == domain['domain_ip'])
        return result

    def to_html_table(self) -> str:
        """
        将域名信息导出为html表格，方便邮件发送

        :rtype: str
        :return: html code
        """

        # 因为google不支持<style>标签，只能全部样式都内联。qq邮箱是支持的
        table_template = """
<figure style="max-width: 900px;overflow-x: auto;margin: 1.2em 0px;padding: 0px;">
    <table style="font-size:12px;border-spacing: 0px;width: 100%;overflow: auto;break-inside: auto;text-align: left;margin: 0.8em 0;padding: 0;word-break: initial;">
        <thead style="background-color:rgb(248,248,248)">
        <tr style="border:1px solid rgb(223,226,229);margin:0px;padding:0px">
            <th style="width:33.3%;border-width:1px 1px 0px;border-top-style:solid;border-right-style:solid;border-left-style:solid;border-top-color:rgb(223,226,229);border-right-color:rgb(223,226,229);border-left-color:rgb(223,226,229);border-bottom-style:initial;border-bottom-color:initial;margin:0px;padding:6px 13px;text-align:left">
                HOSTNAME
            </th>
            <th style="width:33.3%;text-align:left;border-width:1px 1px 0px;border-top-style:solid;border-right-style:solid;border-left-style:solid;border-top-color:rgb(223,226,229);border-right-color:rgb(223,226,229);border-left-color:rgb(223,226,229);border-bottom-style:initial;border-bottom-color:initial;margin:0px;padding:6px 13px">
                DOMAIN
            </th>
            <th style="text-align:left;border-width:1px 1px 0px;border-top-style:solid;border-right-style:solid;border-left-style:solid;border-top-color:rgb(223,226,229);border-right-color:rgb(223,226,229);border-left-color:rgb(223,226,229);border-bottom-style:initial;border-bottom-color:initial;margin:0px;padding:6px 13px">
                ADDRESS/VALUE
            </th>
        </tr>
        </thead>
        <tbody>
        ${trs}
        </tbody>
    </table>
</figure>
        """

        tr_template = """
        <tr style="border:1px solid rgb(223,226,229);margin:0px;padding:0px${background}">
        ${tds}
        </tr>"""

        td_template = '<td style="border:1px solid rgb(223,226,229);padding:6px 13px">${content}</td>'

        count = 1
        trs = ''
        for domain in (self.domains + self.domains_ipv6):
            tr = tr_template.replace('${background}', ';background-color:rgb(248,248,248)' if count % 2 == 0 else '')
            td1 = td_template.replace('${content}', domain['host'])
            td2 = td_template.replace('${content}', domain['domain'])
            td3 = td_template.replace('${content}', domain.get('domain_ip', ''))
            tr = tr.replace('${tds}', td1 + td2 + td3)
            trs = trs + tr
            count = count + 1
        table = table_template.replace('${trs}', trs)
        return table
