import json
import logging
import os
import sys
import time
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from platform import system as pl_system
from subprocess import Popen

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
    auto_restart = False

    ## 运行中调用
    apiRoot = "https://www.namesilo.com/api"
    # ip138的api，由于每年更换一次域名，设为初始化时自动获取api域名
    getIp = ""
    # 添加了两个美国的备用api
    getIPBack1 = "https://api.myip.com"
    getIPBack2 = "https://api.ipify.org?format=json"
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

    # 保存邮件模板
    emailTemplate = {}

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

        if args.get('auto_restart'):
            self.auto_restart = args['auto_restart']

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

        r = None
        try:
            r = httpx.get("https://www.ip138.com/", headers=self.httpHeaders, timeout=10)
            api = r.text.split("<iframe src=\"//")[1]
            api = api.split("/\"")[0]
            self.getIp = api
        except Exception as e:
            self.logger.exception(e)
            if not self.getIp:
                self.logger.info("__init__: 未正确获取ip138的api，将使用备用api")

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
        if not self.getIp:
            try:
                self.get_current_ip_bk()
            except Exception as e:
                self.logger.error("get_current_ip: \tapi error")
                self.check_error()
                self.lastGetCurrentIpError = True
            return

        r = None
        try:
            r = httpx.get('http://' + self.getIp, headers=self.httpHeaders, timeout=10)
        except Exception as e:
            self.logger.exception(e)
            try:
                r = httpx.get('https://' + self.getIp, headers=self.httpHeaders, timeout=10)
            except Exception as e:
                self.logger.exception(e)
                self.check_error()
                self.lastGetCurrentIpError = True

        if r.status_code == 200:
            r = r.text
            r = r.split('您的IP地址是：')[1]
            r = r.split('</title>')[0]
            self.currentIp = r
            self.logger.info("get_current_ip: \tcurrent host ip(ip138): " + r)
            self.lastGetCurrentIpError = False
        else:
            try:
                self.get_current_ip_bk()
            except Exception as e:
                self.logger.exception(e)
                self.logger.error("get_current_ip: \tapi error")
                self.check_error()
                self.lastGetCurrentIpError = True

    def get_current_ip_bk(self):
        # 备用
        r = None
        try:
            r = httpx.get(self.getIPBack1, headers=self.httpHeaders, timeout=10)
            r = r.json()
            self.currentIp = r['ip']
            self.logger.info("get_current_ip: \tcurrent host ip(myip): " + self.currentIp)
            self.lastGetCurrentIpError = False
        except Exception as e:
            self.logger.exception(e)
            r = httpx.get(self.getIPBack2, headers=self.httpHeaders, timeout=10)
            r = r.json()
            self.currentIp = r['ip']
            self.logger.info("get_current_ip: \tcurrent host ip(ipify): " + self.currentIp)
            self.lastGetCurrentIpError = False

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
                self.apiRoot + '/dnsUpdateRecord?version=1&type=xml&rrttl=7207&key=' + self.key + '&domain='
                + self.domain + '&rrid=' + self.rrid + '&rrhost=' + self.host + '&rrvalue=' + new_ip, timeout=10)
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
                    self.send_email('DDNS服务异常提醒 - DNS更新失败', 'send_new_ip.email-template.html', 'new_ip', new_ip)
                self.check_error()
                self.lastUpdateDomainIpError = True
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("update_domain_ip: \tupdate error")
            if not self.lastUpdateDomainIpError:
                self.send_email('DDNS服务异常提醒 - DNS更新失败', 'send_new_ip.email-template.html', 'new_ip', new_ip)
            self.check_error()
            self.lastUpdateDomainIpError = True

    def send_email(self, title, template_file, var_name=None, value=None):
        """
        :param title: 邮件标题
        :param template_file: 模板的单纯文件名，不需要路径
        :param var_name: 模板中的变量名，无需加上${}，只支持一个变量
        :param value: 内存中的变量值
        """
        if not self.emailAlert:
            return -1

        # 加载模板，模板用html文件格式是方便预览
        if not self.emailTemplate.get(template_file):
            with open('conf/' + template_file, 'r', encoding='utf-8') as f:
                self.emailTemplate[template_file] = f.read()
        html_msg = self.emailTemplate[template_file]
        if var_name and value:
            html_msg = self.emailTemplate[template_file].replace('${' + var_name + '}', value)

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
            self.logger.exception(e)

    def check_error(self):
        """
        检查各处的错误，连续错误一定次数后，退出or重启
        """
        if self.lastStartError or self.lastGetCurrentIpError or self.lastUpdateDomainIpError:
            self.errorCount = self.errorCount + 1
        else:
            self.errorCount = 1
        if self.errorCount > 6:
            if pl_system().find('Linux') > -1 and self.auto_restart:
                if self.emailAlert:
                    self.send_email('DDNS服务异常提醒', 'ddns_error_restart.email-template.html')
                self.logger.error("check_error: \trestart - 连续错误6次，程序即将重启")
                # 重启DDNS服务，确保python ddns.py的错误被记录，所以使用sh -c。subprocess.
                # Popen()本身无法单独追加到文件，需要传参stdout为open()文件，但主程序需要退出，让子进程单独运行，所以不可取
                # 这里还是会丢掉sh命令的报错，但是无所谓，影响很小
                Popen(['sh', '-c', 'nohup ' + sys.executable + ' ddns.py 3 >> log/DDNS.log  2>&1 &'])
            else:
                if self.emailAlert:
                    self.send_email('DDNS服务异常提醒', 'ddns_error_exit.email-template.html')
                self.logger.error("check_error: \texit - 连续错误6次，程序退出")
            self.errorCount = 0
            exit(-1)

    def test_email(self):
        """
        调试邮件配置是否正确
        """
        if not self.emailAlert:
            print('Email configuration is not filled')
            return -1
        self.send_email('DDNS Service Test', 'test_email.email-template.html')

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
                        self.send_email('DDNS Service Restarted', 'sys_reboot_ip.email-template.html', 'currentIp',
                                        self.currentIp)
                    else:
                        self.send_email('DDNS Service Restarted', 'sys_reboot_domain.email-template.html', 'domain',
                                        self.host + '.' + self.domain)
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
                self.logger.exception(e)
                self.check_error()
                self.lastStartError = True
            time.sleep(self.frequency)


if __name__ == '__main__':
    """
    不要开代理、梯子，会http连接错误
    """
    if len(sys.argv) > 1:
        if sys.argv[1] == 'archiveLog':
            DDNS.archive_log()
            exit(0)
        # for auto_restart, 避免log上的冲突
        if sys.argv[1].isdigit():
            time.sleep(int(sys.argv[1]))
    ddns = None
    try:
        with open('conf/conf.json', 'r', encoding='utf-8') as fp:
            ddns = DDNS(json.load(fp))
        if len(sys.argv) > 1 and sys.argv[1] == 'testEmail':
            ddns.test_email()
        else:
            ddns.start()
    except BaseException as e:
        ddns.logger.exception(e)
        exit(-1)
