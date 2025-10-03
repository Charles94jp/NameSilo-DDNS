"""
SNMP IPv6 测试脚本

用于测试路由器的 SNMP 配置是否正确，以及能否成功获取 IPv6 地址

使用方法:
  python test_snmp.py
  
或在 Docker 中:
  docker exec namesilo_ddns python /home/NameSilo-DDNS/test_snmp.py
"""

import sys
import logging
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s'
)

def test_snmp_connection(router_ip: str, community: str = 'public', port: int = 161, 
                         snmp_version: int = 2, username: str = None):
    """测试 SNMP 连接"""
    print("=" * 60)
    print("SNMP 连接测试")
    print("=" * 60)
    print(f"路由器 IP: {router_ip}")
    if snmp_version == 3:
        print(f"SNMP 版本: v3")
        print(f"用户名: {username}")
    else:
        print(f"SNMP 版本: v2c")
        print(f"Community: {community}")
    print(f"端口: {port}\n")
    
    try:
        from lib.snmp_client import SNMPClient
        
        snmp = SNMPClient(router_ip, community, port, timeout=10,
                         snmp_version=snmp_version, username=username)
        
        print("正在测试 SNMP 连接...")
        if snmp.test_connection():
            print("[OK] SNMP 连接成功！\n")
            return snmp
        else:
            print("[FAIL] SNMP 连接失败！")
            print("\n可能的原因:")
            if snmp_version == 3:
                print("1. 路由器未启用 SNMPv3 服务")
                print("2. 用户名不正确")
                print("3. 路由器防火墙阻止了 SNMP (UDP 161)")
            else:
                print("1. 路由器未启用 SNMP 服务")
                print("2. Community string 不正确")
                print("3. 路由器防火墙阻止了 SNMP (UDP 161)")
            print("4. 路由器 IP 地址不正确\n")
            return None
            
    except ImportError as e:
        print(f"[FAIL] 导入失败: {e}")
        print("请检查:")
        print("1. 是否安装了 pysnmp: pip install pysnmp")
        print("2. 是否有 lib/snmp_client.py 文件")
        print("3. 当前工作目录是否正确\n")
        return None
    except Exception as e:
        print(f"[FAIL] 连接测试异常: {e}\n")
        import traceback
        traceback.print_exc()
        return None


def test_get_ipv6(snmp):
    """测试获取 IPv6 地址"""
    print("=" * 60)
    print("IPv6 地址获取测试")
    print("=" * 60)
    
    print("正在获取路由器 IPv6 地址...")
    ipv6 = snmp.get_wan_ipv6()
    
    if ipv6 != '-1':
        print(f"[OK] 成功获取到 IPv6: {ipv6}\n")
        
        # 验证地址类型
        if snmp._is_global_unicast(ipv6):
            print("[OK] 这是一个全局单播地址（公网可访问）")
        else:
            print("[WARN] 这不是全局单播地址（可能是本地地址）")
        
        return ipv6
    else:
        print("[FAIL] 获取 IPv6 失败！\n")
        print("可能的原因:")
        print("1. 路由器没有 IPv6 地址")
        print("2. 路由器 SNMP 配置不完整")
        print("3. MIB 权限不足\n")
        return None


def test_with_current_ip(router_ip: str, community: str = 'public'):
    """使用 CurrentIP 类测试"""
    print("=" * 60)
    print("CurrentIP 集成测试")
    print("=" * 60)
    
    try:
        import httpx
        from lib.current_ip import CurrentIP
        
        client = httpx.Client(timeout=30)
        current_ip = CurrentIP(client)
        
        print("通过 CurrentIP.get_router_ipv6_snmp() 获取...")
        ipv6 = current_ip.get_router_ipv6_snmp(router_ip, community)
        
        if ipv6 != '-1':
            print(f"[OK] 成功: {ipv6}\n")
        else:
            print("[FAIL] 失败\n")
        
        client.close()
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}\n")


def main():
    """主函数"""
    print("\n[NameSilo DDNS] SNMP IPv6 测试工具\n")
    
    # 从配置文件读取或使用默认值
    try:
        import json
        with open('conf/conf.json', 'r', encoding='utf-8') as f:
            conf = json.load(f)
            router_snmp = conf.get('router_snmp', {})
            router_ip = router_snmp.get('router_ip', '192.168.1.1')
            community = router_snmp.get('community', 'public')
            port = router_snmp.get('port', 161)
            snmp_version = router_snmp.get('version', 2)
            username = router_snmp.get('username')
    except:
        print("[WARN] 无法读取配置文件，使用默认值\n")
        router_ip = input("请输入路由器 IP [192.168.1.1]: ").strip() or "192.168.1.1"
        snmp_version = int(input("SNMP 版本 [2=v2c, 3=v3] (2): ").strip() or "2")
        if snmp_version == 3:
            username = input("SNMPv3 用户名: ").strip()
            community = 'public'
        else:
            community = input("请输入 SNMP Community [public]: ").strip() or "public"
            username = None
        port = 161
    
    # 测试1: SNMP 连接
    snmp = test_snmp_connection(router_ip, community, port, snmp_version, username)
    
    if snmp:
        # 测试2: 获取 IPv6
        ipv6 = test_get_ipv6(snmp)
        
        if ipv6:
            # 测试3: CurrentIP 集成
            test_with_current_ip(router_ip, community)
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)
    
    print("\n[配置说明] SNMP 配置要点:")
    print("1. 确保路由器启用了 SNMP 服务")
    print("2. 设置正确的 Community String (默认通常是 'public')")
    print("3. 确保防火墙允许 UDP 161 端口")
    print("4. 部分路由器需要在 SNMP 配置中明确允许访问的 IP\n")
    
    print("[参考] 常见路由器 SNMP 配置位置:")
    print("- OpenWrt: 系统 -> SNMP")
    print("- 华硕梅林: 系统管理 -> SNMP")
    print("- iKuai: 高级设置 -> SNMP")
    print("- 小米路由: SSH 进入，修改 /etc/config/snmpd\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试已取消")
        sys.exit(0)
