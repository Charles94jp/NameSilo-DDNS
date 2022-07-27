import argparse
import json
import logging
import os
import ssl
import sys
import time
from datetime import datetime
from platform import system as pl_system

import httpx

from lib.current_ip import CurrentIP
from lib.namesilo_client import NameSiloClient
from lib.email_client import EmailClient


class DDNS:
    """
    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
                2022-07-26 代码重构，拆分模块。
    :since: 2021-12-18
    """

    version = 'NameSilo DDNS v2.2.0'

    _DEBUG_PROXY = 'http://127.0.0.1:8081'

    # 支持低版本的 TLS 1.0
    _SSL_CONTEXT = httpx.create_ssl_context()
    _SSL_CONTEXT.options ^= ssl.OP_NO_TLSv1

    _HTTP_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                   'Chrome/96.0.4664.93 Safari/537.36'}

    _IS_LINUX = True if pl_system().find('Linux') > -1 else False

    def __init__(self, conf: dict, restart_count: int = 0, in_docker: bool = False, debug: bool = False) -> None:
        """

        :param dict conf: 解析后的配置文件
        :param bool debug: 是否在开发调试，调试则启用控制台输出以及网络代理
        """

        if not os.path.isdir('log'):
            os.mkdir('log')
        if os.path.isfile('log/DDNS.log'):
            # size of DDNS.log > 2M
            # logging.handles.TimedRotatingFileHandler, RotatingFileHandler代替FileHandler，即自带的日志滚动，但是命名不可控
            if os.path.getsize('log/DDNS.log') > 2 * 1024 * 1024:
                DDNS.archive_log()
        self.logger = logging.getLogger('NameSilo_DDNS')  # 传logger名称返回新logger，否则返回root，会重复输出到屏幕
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(filename='log/DDNS.log', encoding='utf-8', mode='a')
        formatter = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        if debug:
            fh = logging.StreamHandler()
            fh.setLevel(logging.INFO)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
        self.logger.info("""

 ███╗   ██╗  █████╗  ███╗   ███╗ ███████╗ ███████╗ ██╗ ██╗       ██████╗      ██████╗  ██████╗  ███╗   ██╗ ███████╗
 ████╗  ██║ ██╔══██╗ ████╗ ████║ ██╔════╝ ██╔════╝ ██║ ██║      ██╔═══██╗     ██╔══██╗ ██╔══██╗ ████╗  ██║ ██╔════╝
 ██╔██╗ ██║ ███████║ ██╔████╔██║ █████╗   ███████╗ ██║ ██║      ██║   ██║     ██║  ██║ ██║  ██║ ██╔██╗ ██║ ███████╗
 ██║╚██╗██║ ██╔══██║ ██║╚██╔╝██║ ██╔══╝   ╚════██║ ██║ ██║      ██║   ██║     ██║  ██║ ██║  ██║ ██║╚██╗██║ ╚════██║
 ██║ ╚████║ ██║  ██║ ██║ ╚═╝ ██║ ███████╗ ███████║ ██║ ███████╗ ╚██████╔╝     ██████╔╝ ██████╔╝ ██║ ╚████║ ███████║
 ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚═╝     ╚═╝ ╚══════╝ ╚══════╝ ╚═╝ ╚══════╝  ╚═════╝      ╚═════╝  ╚═════╝  ╚═╝  ╚═══╝ ╚══════╝
 """)

        # 基础配置，分到各模块可以配置base url
        self._base_http_client = httpx.Client(headers=self._HTTP_HEADERS, timeout=30,
                                              verify=False if debug else self._SSL_CONTEXT,
                                              proxies=self._DEBUG_PROXY if debug else None)

        self._current_ip = CurrentIP(self._base_http_client)
        self._namesilo_client = NameSiloClient(self._base_http_client, conf)
        self._email_client = EmailClient(conf)
        self._frequency = conf.get('frequency')
        if self._frequency is None:
            # 默认每次循环休眠10分钟
            self._frequency = 600
        self._email_every_update = conf['email_every_update']
        # todo: auto_restart & email_after_reboot

    @staticmethod
    def archive_log():
        date = time.strftime('%Y%m%d-%H%M%S', time.localtime())
        os.rename('log/DDNS.log', 'log/DDNS-' + date + '.log.back')

    def is_sys_reboot(self):
        """
        适用于家里意外断电后，来电后，路由器重新拨号，导致IP变化的情况
        如果服务器支持来电自启，那么可以邮件提醒这次的IP变化
        todo: docker
        """
        if self.emailAlert and self.email_after_reboot and pl_system().find('Linux') > -1:
            uptime = os.popen('uptime -s').read().strip()
            uptime = datetime.strptime(uptime, '%Y-%m-%d %H:%M:%S')
            # 判断DDNS是随系统启动，还是被手动启动。系统开机到现在的时间差
            if (datetime.now() - uptime).total_seconds() < 4 * 60:

                # 判断是重启，还是关机许久后开机
                # todo: docker
                last_reboot = os.popen('last --system reboot --time-format iso').read().strip()
                last_reboot = last_reboot.split('+')[0].split(' ')[-1]
                last_reboot = datetime.strptime(last_reboot, '%Y-%m-%dT%H:%M:%S')

                last_shutdown = os.popen('last --system shutdown --time-format iso').read().strip()
                last_shutdown = last_shutdown.split('+')[0].split(' ')[-1]
                last_shutdown = datetime.strptime(last_shutdown, '%Y-%m-%dT%H:%M:%S')

                power_outage_duration = last_reboot - last_shutdown
                if power_outage_duration.total_seconds() > 4 * 60:
                    self.get_current_ip()
                    if self.currentIp != self.domains[0]['domainIp']:
                        self.send_email('DDNS Service Restarted', 'sys_reboot_ip.email-template.html', 'currentIp',
                                        self.currentIp)
                    else:
                        self.send_email('DDNS Service Restarted', 'sys_reboot_domain.email-template.html', 'domain',
                                        self.originalDomain.__str__())
                    self.logger.info('is_sys_reboot: system has been rebooted. DDNS successfully sent email alerts.')

    def start(self) -> None:
        """
        开启循环
        """
        # self.is_sys_reboot()
        current_ip = ''
        while True:
            try:
                current_ip = self._current_ip.fetch()
                if not self._namesilo_client.ip_equal(current_ip):
                    r = self._namesilo_client.update_domain_ip(current_ip)
                    if r == 0 and self._email_every_update:
                        self._email_client.send_email('DDNS服务通知：已成功推送新IP地址到NameSilo',
                                                      'update_success.email-template.html', 'new_ip', current_ip)
                    if r != 0:
                        self._email_client.send_email('DDNS服务异常提醒 - DNS更新失败',
                                                      'send_new_ip.email-template.html', 'new_ip', current_ip)
            except Exception as e:
                self.logger.exception(e)
            time.sleep(self._frequency)


def main():
    """
    不要开代理、梯子，会http连接错误
    """
    parser = argparse.ArgumentParser(description='NameSilo DDNS: Regularly detect IP changes of home broadband and '
                                                 'automatically update the IP address of the domain')
    parser.add_argument('--archive', action='store_true', help='Archive logs')
    parser.add_argument('--docker', action='store_true',
                        help='Tell the program that it is now running in a docker container')
    parser.add_argument('-c', help='A magic parameter', dest='count', type=int, default=0)
    parser.add_argument('-v', action='version', version=DDNS.version)
    parser.add_argument('--version', action='version', version=DDNS.version)
    args = parser.parse_args()

    if args.archive:
        DDNS.archive_log()
        sys.exit(0)
    # for auto_restart, 避免log上的冲突
    if args.count > 0:
        time.sleep(5)

    with open('conf/conf.json', 'r', encoding='utf-8') as fp:
        ddns = DDNS(json.load(fp), restart_count=args.count, in_docker=args.docker,
                    debug=True if sys.gettrace() else False)
    if len(sys.argv) > 1 and sys.argv[1] == 'testEmail':
        ddns.test_email()
    else:
        ddns.start()


if __name__ == '__main__':
    main()
