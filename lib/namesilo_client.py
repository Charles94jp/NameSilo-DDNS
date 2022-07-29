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

    def fetch_domains_info(self) -> None:
        """
        拉取域名信息到对象中
        """
        domains_msg = {}
        for domain in self.domains:
            try:
                r = domains_msg.get(domain['domain'])
                if r is None:
                    url = f"/api/dnsListRecords?version=1&type=xml&key={self._api_key}&domain={domain['domain']}"
                    r = self._http_client.get(url)
                    domains_msg[domain['domain']] = r.text
                    if r.status_code != 200:
                        self._logger.error('fetch_domains_info: \tError, process stopped. '
                                           'It could be due to the configuration file error, or the NameSilo server error.')
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
                self._logger.error('fetch_domains_info: \tError, process stopped. '
                                   'It could be due to the configuration file error, or the NameSilo server error.')

    def update_domain_ip(self, new_ip: str) -> int:
        """
        推送新ip到NameSilo

        :param new_ip: 新的ip
        :rtype: int
        :return: 0 if successful, else the inverse of the number of failures
        """
        success1 = 10000
        error2 = 20000
        error3 = 30000
        for domain in self.domains:
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
                    self._logger.info(f"update_domain_ip: \tupdate '{full_domain}' "
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
                    self._logger.error(f"update_domain_ip: \tupdate '{full_domain}' failed. "
                                       f"Namesilo response:\n{r1}")
            except Exception as e:
                error3 = error3 + 1
                self._logger.exception(e)
                self._logger.error(f"update_domain_ip: \tupdate '{full_domain}' error")
        if success1 > 10000:
            return 0
        if error2 > 20000:
            return -(error2 - 20000)
        if error3 > 30000:
            return -(error3 - 30000)

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
        for domain in self.domains:
            tr = tr_template.replace('${background}', ';background-color:rgb(248,248,248)' if count % 2 == 0 else '')
            td1 = td_template.replace('${content}', domain['host'])
            td2 = td_template.replace('${content}', domain['domain'])
            td3 = td_template.replace('${content}', domain.get('domain_ip', ''))
            tr = tr.replace('${tds}', td1 + td2 + td3)
            trs = trs + tr
            count = count + 1
        table = table_template.replace('${trs}', trs)
        return table
