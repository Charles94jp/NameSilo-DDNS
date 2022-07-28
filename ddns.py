import argparse
import json
import logging
import os
import ssl
import sys
import time
from datetime import datetime
from platform import system as pl_system
from subprocess import Popen

import httpx

from lib.current_ip import CurrentIP
from lib.namesilo_client import NameSiloClient
from lib.email_client import EmailClient


class DDNS:
    """
    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
                2022-07-27 代码重构，引入argparse，移除email_after_reboot，新的重启及计数机制
                2022-07-26 代码重构，拆分出三个子模块，优化代码风格，取消缓存邮件模板，取消日志回滚时压缩，添加ASCII启动图标
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

    def __init__(self, conf: dict, restart_count: int = 0, debug: bool = False) -> None:
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
        self._logger = logging.getLogger('NameSilo_DDNS')  # 传logger名称返回新logger，否则返回root，会重复输出到屏幕
        self._logger.setLevel(logging.INFO)
        fh = logging.FileHandler(filename='log/DDNS.log', encoding='utf-8', mode='a')
        formatter = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        self._logger.addHandler(fh)
        if debug:
            fh = logging.StreamHandler()
            fh.setLevel(logging.INFO)
            fh.setFormatter(formatter)
            self._logger.addHandler(fh)
        self._logger.info("""

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
        self._email_client = EmailClient(conf, debug=debug)
        self._frequency = conf.get('frequency')
        if self._frequency is None:
            # 默认每次循环休眠10分钟
            self._frequency = 600
        self._email_every_update = conf['email_every_update']
        # is_sys_reboot is deprecated
        # self._email_after_reboot = conf['email_after_reboot']
        # self._in_docker = in_docker
        self._restart_count = restart_count
        self._auto_restart = conf['auto_restart']

    @staticmethod
    def archive_log():
        date = time.strftime('%Y%m%d-%H%M%S', time.localtime())
        os.rename('log/DDNS.log', 'log/DDNS-' + date + '.log.back')

    def test_email(self):
        """
        调试邮件配置是否正确
        """
        if not self._email_client.available:
            print('Email configuration is not filled')
            sys.exit(-1)
        self._logger.info('test_email')
        self._email_client.send_email('DDNS服务通知 - 测试邮件', 'test_email.email-template.html',
                                      self._namesilo_client.to_html_table())
        print('The test email has been sent')

    def is_sys_reboot(self):
        """
        适用于家里意外断电后，来电后，路由器重新拨号，导致IP变化的情况
        如果服务器支持来电自启，那么可以邮件提醒这次的IP变化
        deprecated:
            1.该功能实际用处不大，监控家里停电、来电可以通过其它渠道，不需要本程序
            2.如果来电，路由器程序拨号，IP变化，本程序有邮件提醒
            3.docker中判断是否是长时间关机后启动，需要读取/var/log/wtmp文件，alpine没有last命令可以读取。而python utmp则不方便
        """
        import warnings
        warnings.warn("this is deprecated", DeprecationWarning, 2)
        if self._email_client.available and self._email_after_reboot and pl_system().find('Linux') > -1:
            uptime = os.popen('uptime -s').read().strip()
            uptime = datetime.strptime(uptime, '%Y-%m-%d %H:%M:%S')
            # 判断DDNS是随系统启动，还是被手动启动。系统开机到现在的时间差
            if (datetime.now() - uptime).total_seconds() < 4 * 60:

                # 判断系统这次启动是重启，还是关机许久后开机
                # 容器通过 -v /var/log/wtmp:/home/wtmp:rw 挂载宿主机文件进行
                cmd = f"last --system reboot --time-format iso {'-f /home/wtmp' if self._in_docker else ''}"
                last_reboot = os.popen(cmd).read().strip()
                last_reboot = last_reboot.split('+')[0].split(' ')[-1]
                last_reboot = datetime.strptime(last_reboot, '%Y-%m-%dT%H:%M:%S')

                cmd = f"last --system shutdown --time-format iso {'-f /home/wtmp' if self._in_docker else ''}"
                last_shutdown = os.popen(cmd).read().strip()
                last_shutdown = last_shutdown.split('+')[0].split(' ')[-1]
                last_shutdown = datetime.strptime(last_shutdown, '%Y-%m-%dT%H:%M:%S')

                power_outage_duration = last_reboot - last_shutdown
                if power_outage_duration.total_seconds() > 4 * 60:
                    pass

    def start(self) -> None:
        """
        开启循环
        todo: 邮件支持中英文
        """
        self._namesilo_client.fetch_domains_info()
        current_ip = ''
        while True:
            try:
                current_ip = self._current_ip.fetch()
                # 值得注意的是，当程序在运行一段时间后，而用户手动去NameSilo修改了域名的解析值，由于程序只对比内存中的值，所以不会触发更新
                if not self._namesilo_client.ip_equal(current_ip):
                    r = self._namesilo_client.update_domain_ip(current_ip)
                    if r == 0 and self._email_every_update:
                        self._email_client.send_email('DDNS服务通知 - 已成功推送新IP地址到NameSilo',
                                                      'update_successful.email-template.html',
                                                      self._namesilo_client.to_html_table(), 'new_ip', current_ip)
                    if r != 0:
                        self._email_client.send_email('DDNS服务异常提醒 - DNS更新失败',
                                                      'update_failed.email-template.html',
                                                      self._namesilo_client.to_html_table(), 'new_ip', current_ip)
            except Exception as e:
                self._logger.exception(e)
                if self._auto_restart:
                    if self._restart_count > 10:
                        self._email_client.send_email('DDNS服务异常提醒 - 程序已停止', 'ddns_error_exit.email-template.html',
                                                      self._namesilo_client.to_html_table())
                        self._logger.info('程序连续错误10次，自动退出')
                        sys.exit(-1)
                    time.sleep(self._frequency)
                    # 重启DDNS服务，确保python ddns.py的错误被记录，所以使用sh -c。subprocess.
                    # Popen()本身无法单独追加到文件，需要传参stdout为open()文件，但主程序需要退出，让子进程单独运行，所以不可取
                    # 这里还是会丢掉sh命令的报错，但是无所谓，影响很小
                    Popen(['sh', '-c',
                           f'nohup {sys.executable} ddns.py -c {self._restart_count + 1}>> log/DDNS.log  2>&1 &'])
                    sys.exit(-1)
            self._restart_count = 0
            time.sleep(self._frequency)


def main():
    """
    不要开代理、梯子，会http连接错误
    """
    parser = argparse.ArgumentParser(description='NameSilo DDNS: Regularly detect IP changes of home broadband and '
                                                 'automatically update the IP address of the domain')
    parser.add_argument('--archive', action='store_true', help='Archive logs')
    parser.add_argument('--test-email', action='store_true', help='Send a test email and exit')
    parser.add_argument('-c', help='A magic parameter', dest='count', type=int, default=0)
    parser.add_argument('-v', '--version', action='version', version=DDNS.version)
    args = parser.parse_args()

    if args.archive:
        DDNS.archive_log()
        sys.exit(0)
    # for auto_restart, 避免log上的冲突
    if args.count > 0:
        time.sleep(5)

    with open('conf/conf.json', 'r', encoding='utf-8') as fp:
        ddns = DDNS(json.load(fp), restart_count=args.count, debug=True if sys.gettrace() else False)
    if args.test_email:
        ddns.test_email()
    else:
        ddns.start()


if __name__ == '__main__':
    main()
