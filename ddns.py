import json
import logging
import os
import sys
import time
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from platform import system as pl_system

import httpx


class DDNS:
    ## 通过配置文件初始化
    key = ''
    # 配置中domain = host.domain，host为子域名前缀
    domain = ''
    host = ''
    frequency = 600
    emailAlert = False
    mail_host = ''
    mail_port = ''
    mail_user = ''
    mail_pass = ''
    receivers = []
    email_after_reboot = False

    ## 运行中调用
    apiRoot = "https://www.namesilo.com/api"
    getIp = "2021.ip138.com"
    domainIp = ''
    currentIp = ''
    logger = None
    httpHeaders = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                 'Chrome/96.0.4664.93 Safari/537.36'}
    rrid = ''
    errorCount = 0
    lastGetCurrentIpError = False
    lastUpdateDomainIpError = False
    lastStartError = False

    def __init__(self, args, debug=False):
        """
        set attributes，set logger
        :param args: dict
        """
        self.key = args['key']
        tmp = args['domain']
        tmp = tmp.split('.')
        self.domain = tmp[-2] + '.' + tmp[-1]
        self.host = tmp[0]
        if args.get('frequency'):
            self.frequency = args['frequency']

        if args['mail_host'] and args['mail_port'] and args['mail_user'] and args['mail_pass'] and args['receivers']:
            self.emailAlert = True
            self.mail_host = args['mail_host']
            self.mail_port = args['mail_port']
            self.mail_user = args['mail_user']
            self.mail_pass = args['mail_pass']
            self.receivers = args['receivers']

        if args.get('email_after_reboot'):
            self.email_after_reboot = args['email_after_reboot']

        if not os.path.isdir('log'):
            os.mkdir('log')
        if os.path.isfile('log/DDNS.log'):
            # size of DDNS.log > 2M
            # logging.handles.TimedRotatingFileHandler, RotatingFileHandler代替FileHandler，即自带的日志滚动，但是命名不可控
            if os.path.getsize('log/DDNS.log') > 2 * 1024 * 1024:
                DDNS.archive_log()
        self.logger = logging.getLogger('DDNS')  # 传logger名称返回新logger，否则返回root，会重复输出到屏幕
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(filename='log/DDNS.log', encoding='utf-8', mode='a')
        formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        if debug:
            fh = logging.StreamHandler()
            self.logger.addHandler(fh)
        self.logger.info('\n\nstarting...')

    @staticmethod
    def archive_log():
        date = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        if pl_system().find('Linux') > -1:
            os.system('gzip -N log/DDNS.log && mv log/DDNS.log.gz log/DDNS-' + date + '.log.gz')
        else:
            os.rename('log/DDNS.log', 'log/DDNS-' + date + '.log.back')

    def get_current_ip(self):
        """
        高频使用 api
        update self.currentIp
        :return: None
        """
        r = None
        try:
            r = httpx.get('http://' + self.getIp, headers=self.httpHeaders, timeout=10)
        except Exception as e:
            self.logger.exception(e)
            r = httpx.get('https://' + self.getIp, headers=self.httpHeaders, timeout=10)

        if r.status_code == 200:
            r = r.text
            r = r.split('您的IP地址是：')[1]
            r = r.split('</title>')[0]
            self.currentIp = r
            self.logger.info("get_current_ip: \tcurrent host ip: " + r)
            self.lastGetCurrentIpError = False
        else:
            self.logger.error("get_current_ip: \tapi error")
            self.check_error()
            self.lastGetCurrentIpError = True

    def get_domain_ip(self):
        """
        update self.domainIp
        :return: None
        """
        try:
            r = httpx.get(
                self.apiRoot + '/dnsListRecords?version=1&type=xml&key=' + self.key + '&domain=' + self.domain,
                timeout=10)
            if r.status_code == 200:
                r = r.text.split('<resource_record>')
                for record in r:
                    if record.find(self.host + '.' + self.domain) != -1:
                        r = record
                        break
                r = r.split('</record_id>')
                self.rrid = r[0].split('<record_id>')[-1]
                self.domainIp = r[1].split('<value>')[1].split('</value>')[0]
                self.logger.info("get_domain_ip: \tcurrent domain name resolution ip: " + self.domainIp)
            else:
                self.logger.error("get_domain_ip: \tError, process stopped. "
                                  "It could be due to the configuration file error, or the NameSilo server error.")
                exit(-1)
        except httpx.ConnectError as e:
            self.logger.exception(e)
            self.logger.error("get_domain_ip: \tError, process stopped. "
                              "It could be due to the configuration file error, or the NameSilo server error.")
            exit(-1)

    def update_domain_ip(self, new_ip):
        """
        重要 api
        更新域名解析，更新self.domainIp
        :return: None
        """
        try:
            r = httpx.get(
                self.apiRoot + '/dnsUpdateRecord?version=1&type=xml&rrttl=7207&key=' + self.key + '&domain=' + self.domain
                + '&rrid=' + self.rrid + '&rrhost=' + self.host + '&rrvalue=' + new_ip,
                timeout=10)
            r = r.text
            r1 = r
            r = r.split('<code>')[1]
            r = r.split('</code>')[0]
            if r == '300':
                self.domainIp = new_ip
                self.logger.info("update_domain_ip: \tupdate completed: " + self.domainIp)
                self.lastUpdateDomainIpError = False
            else:
                self.logger.error("update_domain_ip: \tupdate failed. Namesilo response:\n" + r1)
                if not self.lastUpdateDomainIpError:
                    self.send_new_ip(new_ip)
                self.check_error()
                self.lastUpdateDomainIpError = True
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("update_domain_ip: \tupdate error")
            if not self.lastUpdateDomainIpError:
                self.send_new_ip(new_ip)
            self.check_error()
            self.lastUpdateDomainIpError = True

    def send_new_ip(self, new_ip):
        """
        when update_domain_ip error
        """
        self.send_email('DDNS服务异常提醒 - DNS更新失败',
                        '<p class="MsoNormal"><span style="font-family:宋体;color:black">您好！</span></p>'
                        '<p class="MsoNormal" style="text-indent:21.0pt"><span style="font-family:宋体;color:black">'
                        '您的IP已发生变更，当前IP是：<a href="' + new_ip + '">' + new_ip +
                        '</a>，但由于网络错误，DDNS无法推送您的新IP到NameSilo。DDNS服务不会立即停止，'
                        '它将再尝试几次推送。</span></p><p class="MsoNormal" style="text-indent:21.0pt">'
                        '<span style="font-family:宋体;color:black">您可以登录服务器通过log/DDNS.log文件查看异常细明，'
                        '<b>请尽快排查原因并重启DDNS服务</b>，避免IP变动导致您的服务器无法通过域名访问。</span></p>'
                        '<p class="MsoNormal" style="text-indent:21.0pt"><span style="font-family:宋体;color:black">'
                        '有任何问题请在<a target="_blank" href="https://github.com/Charles94jp/NameSilo-DDNS">'
                        'DDNS项目的GitHub Issues</a>中反馈，谢谢您的支持</span></p>')

    def send_email(self, title, html_msg):
        if not self.emailAlert:
            return -1
        # 邮件消息，plain是纯文本，html可以自定义样式
        message = MIMEText(html_msg, 'html', 'utf-8')
        # 邮件主题
        message['Subject'] = title
        # 发送方信息
        message['From'] = self.mail_user
        # 接受方信息
        message['To'] = ','.join(self.receivers)

        # 登录并发送邮件
        try:
            smtpObj = smtplib.SMTP_SSL(self.mail_host, int(self.mail_port))
            # 连接到服务器
            # 登录到服务器
            smtpObj.login(self.mail_user, self.mail_pass)
            # 发送
            smtpObj.sendmail(
                self.mail_user, self.receivers, message.as_string())
            # 退出
            smtpObj.quit()
            self.logger.info("send_email: \tsuccess")
        except smtplib.SMTPException as e:
            ddns.logger.exception(e)

    def check_error(self):
        if self.lastStartError or self.lastGetCurrentIpError or self.lastUpdateDomainIpError:
            self.errorCount = self.errorCount + 1
        else:
            self.errorCount = 1
        if self.errorCount > 12:
            if self.emailAlert:
                self.send_email('DDNS服务异常提醒',
                                '<p class="MsoNormal"><span style="font-family:宋体;color:black">您好！</span></p>'
                                '<p class="MsoNormal" style="text-indent:21.0pt"><span style="font-family:宋体;'
                                'color:black">您的DDNS服务因异常已停止，这并非是服务本身导致的，可能是ip138.com或NameSilo的api'
                                '繁忙所致。</span></p><p class="MsoNormal" style="text-indent:21.0pt"><span '
                                'style="font-family:宋体;color:black">您可以登录服务器通过log/DDNS.log文件查看异常细明，<b>请尽快排查原因'
                                '并重启DDNS服务</b>，避免IP变动导致您的服务器无法通过域名访问。</span></p><p class="MsoNormal"'
                                ' style="text-indent:21.0pt"><span style="font-family:宋体;color:black">有任何问题请在'
                                '<a target="_blank" href="https://github.com/Charles94jp/NameSilo-DDNS">DDNS项目的'
                                'GitHub Issues</a>中反馈，谢谢您的支持</span></p>')
            self.errorCount = 0
            self.logger.error("start: \t连续错误12次，程序退出")
            exit(-1)

    def test_email(self):
        """
        调试邮件配置是否正确
        """
        if not self.emailAlert:
            print('Email configuration is not filled')
            return -1
        self.send_email('DDNS Service Test',
                        '这是<a target="_blank" href="https://github.com/Charles94jp/NameSilo-DDNS">DDNS服务'
                        '</a>的测试邮件，收到此邮件代表你的邮件配置无误')

    def is_sys_reboot(self):
        """
        适用于家里意外断电后，来电后，路由器重新拨号，导致IP变化的情况
        如果服务器支持来电自启，那么可以邮件提醒这次的IP变化
        """
        if self.emailAlert and self.email_after_reboot and pl_system().find('Linux') > -1:
            uptime = os.popen('uptime -s').read().strip()
            uptime = datetime.strptime(uptime, '%Y-%m-%d %H:%M:%S')
            # 判断DDNS是随系统启动，还是被手动启动。系统开机到现在的时间差
            if (datetime.now() - uptime).total_seconds() < 4 * 60:

                # 判断是重启，还是关机许久后开机
                last_reboot = os.popen('last --system reboot --time-format iso').read().strip()
                last_reboot = last_reboot.split('+')[0].split(' ')[-1]
                last_reboot = datetime.strptime(last_reboot, '%Y-%m-%dT%H:%M:%S')

                last_shutdown = os.popen('last --system shutdown --time-format iso').read().strip()
                last_shutdown = last_shutdown.split('+')[0].split(' ')[-1]
                last_shutdown = datetime.strptime(last_shutdown, '%Y-%m-%dT%H:%M:%S')

                power_outage_duration = last_reboot - last_shutdown
                if power_outage_duration.total_seconds() > 4 * 60:

                    self.get_current_ip()
                    if self.currentIp != self.domainIp:
                        self.send_email('DDNS Service Restarted',
                                        '<p class="MsoNormal"><span style="font-family:宋体;color:black">您好！</span></p>'
                                        '<p class="MsoNormal"style="text-indent:21.0pt">'
                                        '<span style="font-family:宋体;color:black">您的DDNS服务检测到您的服务器意外停止后重新启动。'
                                        '您的IP已发生变更，当前IP是：<a href="' + self.currentIp + '">' + self.currentIp +
                                        '</a></span></p><p class="MsoNormal"style="text-indent:21.0pt">'
                                        '<span style="font-family:宋体;color:black">因为您设置了<a target="_blank" '
                                        'href="https://github.com/Charles94jp/NameSilo-DDNS#configuration">'
                                        'email_after_reboot</a>选项，所以收到了此邮件。</span></p>'
                                        '<p class="MsoNormal"style="text-indent:21.0pt">'
                                        '<span style="font-family:宋体;color:black">此邮件意在提醒您：您的服务器已正常启动。'
                                        '如果您在手动开关机服务器，请忽略此邮件</span></p>')
                    else:
                        self.send_email('DDNS Service Restarted',
                                        '<p class="MsoNormal"><span style="font-family:宋体;color:black">您好！</span></p>'
                                        '<p class="MsoNormal"style="text-indent:21.0pt">'
                                        '<span style="font-family:宋体;color:black">您的DDNS服务检测到您的服务器意外停止后重新启动。'
                                        '您的IP未发生变更，您可以通过域名：<a>' + self.host + '.' + self.domain +
                                        '</a>正常访问</span></p><p class="MsoNormal"style="text-indent:21.0pt">'
                                        '<span style="font-family:宋体;color:black">因为您设置了<a target="_blank" '
                                        'href="https://github.com/Charles94jp/NameSilo-DDNS#configuration">'
                                        'email_after_reboot</a>选项，所以收到了此邮件。</span></p>'
                                        '<p class="MsoNormal"style="text-indent:21.0pt">'
                                        '<span style="font-family:宋体;color:black">此邮件意在提醒您：您的服务器已正常启动。'
                                        '如果您在手动开关机服务器，请忽略此邮件</span></p>')
                    self.logger.info("is_sys_reboot: system has been rebooted. DDNS successfully sent email alerts.")

    def start(self):
        self.get_domain_ip()
        self.is_sys_reboot()
        while True:
            try:
                self.get_current_ip()
                if self.currentIp != self.domainIp:
                    self.update_domain_ip(self.currentIp)
                self.lastStartError = False
            except Exception as e:
                ddns.logger.exception(e)
                self.check_error()
                self.lastStartError = True
            time.sleep(self.frequency)


if __name__ == '__main__':
    """
    不要开代理、梯子，会http连接错误
    """
    if len(sys.argv) > 1 and sys.argv[1] == 'archiveLog':
        DDNS.archive_log()
        exit(0)
    ddns = None
    try:
        with open('conf.json', 'r') as fp:
            ddns = DDNS(json.load(fp))
        if len(sys.argv) > 1 and sys.argv[1] == 'testEmail':
            ddns.test_email()
        else:
            ddns.start()
    except BaseException as e:
        ddns.logger.exception(e)
        exit(-1)
