import logging
import smtplib
from email.utils import formataddr
from email.mime.text import MIMEText


class EmailClient:
    """
    邮件客户端，负责读取模板、发送邮件

    `NameSilo DDNS <https://github.com/Charles94jp/NameSilo-DDNS>`_

    :author: Charles94jp
    :changelog: 20xx-xx-xx: xxx
                2022-07-26 代码重构，拆分出此类，由于邮件使用频率不高，取消在内存中缓存模板内容
    :since: 2022-07-26
    """
    available = False

    def __init__(self, conf: dict, debug: bool = False) -> None:
        """

        :param dict conf: 解析后的配置文件
        """
        self._logger = logging.getLogger('NameSilo_DDNS')
        self._debug = debug
        if conf['mail_host'] and conf['mail_port'] and conf['mail_user'] and conf['mail_pass'] and conf['receivers']:
            self.available = True
            self._mail_host = conf['mail_host']
            self._mail_port = conf['mail_port']
            self._mail_user = conf['mail_user']
            self._mail_pwd = conf['mail_pass']
            self._receivers = conf['receivers']
            self._zh_cn = True
            lang = conf['mail_lang'].lower()
            if lang == 'en' or lang == 'en-us':
                self._zh_cn = False

    def send_email(self, template_file_name, domain_table=None, var_name=None, value=None):
        """
        从邮件模板中读取邮件标题和内容，替换变量，拼接domain table后发送

        :param str template_file_name: 模板的单纯文件名，不需要路径，不要.email-template.html后缀
        :param str domain_table:
        :param str var_name: 模板中的变量名，无需加上${}，只支持一个变量
        :param * value: 内存中的变量值
        """
        if not self.available:
            return -1

        # 加载模板，模板用html文件格式是方便预览
        with open(f'conf/{template_file_name}.email-template{"" if self._zh_cn else "-en"}.html',
                  'r', encoding='utf-8') as f:
            template = f.read()
        template = template.split('<!--email title-->')
        title = template[0]
        html_msg = template[1]
        if var_name is not None and value is not None:
            html_msg = html_msg.replace('${' + var_name + '}', value)

        html_msg = html_msg + domain_table

        # 邮件消息，plain是纯文本，html可以自定义样式
        message = MIMEText(html_msg, 'html', 'utf-8')
        # 邮件主题
        message['Subject'] = title
        # 发送方信息
        message['From'] = formataddr(('DDNS Service', self._mail_user))
        # 接受方信息
        message['To'] = ','.join(self._receivers)

        # 登录并发送邮件
        try:
            if self._debug:
                import socks
                socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, '127.0.0.1', 7890)
                socks.wrapmodule(smtplib)
            smtp_client = smtplib.SMTP_SSL(self._mail_host, int(self._mail_port))
            # 连接到服务器
            # 登录到服务器
            r = smtp_client.login(self._mail_user, self._mail_pwd)
            # 发送
            r = smtp_client.sendmail(
                self._mail_user, self._receivers, message.as_string())
            # 退出
            r = smtp_client.quit()
            self._logger.info('send_email: \tsuccess')
        except smtplib.SMTPException as e:
            self._logger.exception(e)
