import logging
import re
from typing import Optional

from pysnmp.hlapi import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    getCmd,
    nextCmd
)


class SNMPClient:
    """
    SNMP 客户端，用于从路由器获取 IPv6 地址
    
    :author: Resurrection2981
    :since: 2025-10-03
    """
    
    # IPv6 地址验证正则（与 CurrentIP 保持一致）
    _VALID_V6_EXP = re.compile(r'^(([0-9A-Fa-f]{1,4}:){1,6})(:|[0-9A-Fa-f]{1,4}:)([0-9A-Fa-f]{1,4})$')
    
    # SNMP OID 定义
    # IP-MIB::ipAddressIfIndex - 获取 IPv6 地址列表
    OID_IP_ADDRESS_IF_INDEX = '1.3.6.1.2.1.4.34.1.3'
    # IP-MIB::ipAddressType - 地址类型 (1=IPv4, 2=IPv6)
    OID_IP_ADDRESS_TYPE = '1.3.6.1.2.1.4.34.1.4'
    # IP-MIB::ipAddressPrefix
    OID_IP_ADDRESS_PREFIX = '1.3.6.1.2.1.4.32.1.5'
    
    def __init__(self, router_ip: str, community: str = 'public', port: int = 161, timeout: int = 5):
        """
        初始化 SNMP 客户端
        
        :param router_ip: 路由器 IP 地址
        :param community: SNMP community string (默认 'public')
        :param port: SNMP 端口 (默认 161)
        :param timeout: 超时时间（秒）
        """
        self._router_ip = router_ip
        self._community = community
        self._port = port
        self._timeout = timeout
        self._logger = logging.getLogger(self.__class__.__name__)
    
    def get_wan_ipv6(self, interface_index: Optional[int] = None) -> str:
        """
        获取路由器 WAN 口的 IPv6 地址
        
        :param interface_index: 网络接口索引，如果为 None 则自动查找第一个全局单播地址
        :return: IPv6 地址字符串，失败返回 '-1'
        """
        try:
            # 方法1: 遍历所有 IPv6 地址，找到全局单播地址（Global Unicast）
            ipv6_addresses = self._get_all_ipv6_addresses()
            
            if not ipv6_addresses:
                self._logger.warning('No IPv6 addresses found via SNMP')
                return '-1'
            
            # 过滤出全局单播地址（2000::/3 范围）
            global_addresses = [
                ip for ip in ipv6_addresses 
                if self._is_global_unicast(ip)
            ]
            
            if not global_addresses:
                self._logger.warning(f'No global unicast IPv6 found. All addresses: {ipv6_addresses}')
                return '-1'
            
            # 如果有多个，返回第一个（通常是 WAN 口）
            result_ip = global_addresses[0]
            
            if self.valid_v6(result_ip):
                self._logger.info(f'Router WAN IPv6 via SNMP: {result_ip}')
                return result_ip
            else:
                self._logger.error(f'Invalid IPv6 format: {result_ip}')
                return '-1'
                
        except Exception as e:
            self._logger.exception(f'SNMP query failed: {e}')
            return '-1'
    
    def _get_all_ipv6_addresses(self) -> list:
        """
        获取路由器上所有的 IPv6 地址
        
        :return: IPv6 地址列表
        """
        ipv6_list = []
        
        try:
            # 使用 nextCmd 遍历 IP-MIB::ipAddressIfIndex 表
            iterator = nextCmd(
                SnmpEngine(),
                CommunityData(self._community),
                UdpTransportTarget((self._router_ip, self._port), timeout=self._timeout, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity(self.OID_IP_ADDRESS_IF_INDEX)),
                lexicographicMode=False
            )
            
            for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication:
                    self._logger.error(f'SNMP error: {errorIndication}')
                    break
                elif errorStatus:
                    self._logger.error(f'SNMP error: {errorStatus.prettyPrint()}')
                    break
                else:
                    for varBind in varBinds:
                        oid = varBind[0].prettyPrint()
                        value = varBind[1].prettyPrint()
                        
                        # 从 OID 中提取 IPv6 地址
                        # OID 格式: 1.3.6.1.2.1.4.34.1.3.2.16.x.x.x...
                        # 其中 .2.16 表示 IPv6 (type=2, len=16)
                        ipv6 = self._extract_ipv6_from_oid(oid)
                        if ipv6 and ipv6 not in ipv6_list:
                            ipv6_list.append(ipv6)
                            self._logger.debug(f'Found IPv6: {ipv6}')
            
            return ipv6_list
            
        except Exception as e:
            self._logger.exception(f'Failed to get IPv6 addresses: {e}')
            return []
    
    def _extract_ipv6_from_oid(self, oid: str) -> Optional[str]:
        """
        从 SNMP OID 中提取 IPv6 地址
        
        OID 格式: 1.3.6.1.2.1.4.34.1.3.2.16.32.14.3.123.80.10.87.167.213.46.52.191.9.19.235.105
        最后16个数字是 IPv6 的 16 个字节
        
        :param oid: SNMP OID 字符串
        :return: IPv6 地址或 None
        """
        try:
            parts = oid.split('.')
            
            # 查找 .2.16 标记（IPv6 类型和长度）
            for i in range(len(parts) - 17):
                if parts[i] == '2' and parts[i + 1] == '16':
                    # 提取接下来的 16 个字节
                    bytes_list = [int(parts[i + 2 + j]) for j in range(16)]
                    
                    # 转换为 IPv6 格式
                    ipv6 = ':'.join([
                        f'{bytes_list[j]:02x}{bytes_list[j+1]:02x}'
                        for j in range(0, 16, 2)
                    ])
                    
                    # 简化 IPv6 地址（移除前导零）
                    ipv6 = self._simplify_ipv6(ipv6)
                    
                    return ipv6
            
            return None
            
        except Exception as e:
            self._logger.debug(f'Failed to extract IPv6 from OID {oid}: {e}')
            return None
    
    def _simplify_ipv6(self, ipv6: str) -> str:
        """
        简化 IPv6 地址格式（移除前导零，但不压缩连续的0）
        
        :param ipv6: 完整的 IPv6 地址
        :return: 简化后的 IPv6 地址
        """
        try:
            # 分割并移除每段的前导零
            segments = ipv6.split(':')
            simplified = [seg.lstrip('0') or '0' for seg in segments]
            return ':'.join(simplified)
        except:
            return ipv6
    
    def _is_global_unicast(self, ipv6: str) -> bool:
        """
        判断是否为全局单播地址（Global Unicast Address）
        
        全局单播地址范围: 2000::/3 (二进制以 001 开头)
        排除:
        - 链路本地地址 fe80::/10
        - 唯一本地地址 fc00::/7
        - 多播地址 ff00::/8
        
        :param ipv6: IPv6 地址
        :return: True 如果是全局单播地址
        """
        try:
            first_segment = ipv6.split(':')[0]
            first_byte = int(first_segment, 16)
            
            # 全局单播: 2000::/3 = 0x2000-0x3FFF
            # 二进制: 001x xxxx xxxx xxxx
            if 0x2000 <= first_byte <= 0x3FFF:
                return True
            
            # 排除特殊地址
            if ipv6.startswith('fe80:'):  # 链路本地
                return False
            if ipv6.startswith('fc') or ipv6.startswith('fd'):  # 唯一本地
                return False
            if ipv6.startswith('ff'):  # 多播
                return False
            
            return False
            
        except:
            return False
    
    @staticmethod
    def valid_v6(ip: str) -> bool:
        """
        验证 IPv6 地址格式
        
        :param ip: IPv6 地址字符串
        :return: True 如果格式有效
        """
        return SNMPClient._VALID_V6_EXP.match(ip) is not None
    
    def test_connection(self) -> bool:
        """
        测试 SNMP 连接是否正常
        
        :return: True 如果连接成功
        """
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self._community),
                UdpTransportTarget((self._router_ip, self._port), timeout=self._timeout, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication:
                self._logger.error(f'SNMP connection test failed: {errorIndication}')
                return False
            elif errorStatus:
                self._logger.error(f'SNMP connection test failed: {errorStatus.prettyPrint()}')
                return False
            else:
                sys_desc = varBinds[0][1].prettyPrint()
                self._logger.info(f'SNMP connection successful. Device: {sys_desc}')
                return True
                
        except Exception as e:
            self._logger.exception(f'SNMP connection test exception: {e}')
            return False
