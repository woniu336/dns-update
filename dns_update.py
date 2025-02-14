import socket
import time
import requests
import hmac
import hashlib
import base64
import urllib.parse
import os
import re
import subprocess

# Cloudflare 配置
api_key = ''
email = ''
zone_id = ''

# 钉钉机器人配置
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
SECRET = "YOUR_SECRET"

# 服务器备注（将由 Bash 脚本更新）
SERVER_REMARK = ""

def generate_sign():
    # 生成钉钉机器人签名
    timestamp = str(round(time.time() * 1000))
    secret_enc = SECRET.encode('utf-8')
    string_to_sign = f'{timestamp}\n{SECRET}'
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign

def send_dingtalk_notification(message):
    # 在消息前添加服务器备注
    if SERVER_REMARK:
        message = f"[{SERVER_REMARK}] {message}"
    
    # 发送钉钉通知
    timestamp, sign = generate_sign()
    webhook_url = f"https://oapi.dingtalk.com/robot/send?access_token={ACCESS_TOKEN}&timestamp={timestamp}&sign={sign}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "msgtype": "text",
        "text": {
            "content": message
        },
        "at": {
            "isAtAll": False
        }
    }
    
    response = requests.post(webhook_url, headers=headers, json=data)
    print(f"钉钉通知发送状态: {response.status_code}")
    print(f"钉钉通知响应: {response.text}")

def check_tcp_port(server_ip, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 设置超时时间为5秒
        result = sock.connect_ex((server_ip, port))
        if result == 0:
            return True  # TCP端口连通
        else:
            return False  # TCP端口不连通
    except Exception as e:
        print(f"Error occurred while checking TCP port: {e}")
        return False

def update_dns_record(subdomain, ip, proxied=False):
    try:
        dns_record_id = dns_record_ids[subdomain]  # 查找子域名对应的 DNS 记录 ID
        # 使用Cloudflare API 更新 DNS 记录
        headers = {
            'X-Auth-Email': email,
            'X-Auth-Key': api_key,
            'Content-Type': 'application/json'
        }

        data = {
            'type': 'A',
            'name': subdomain,
            'content': ip,
            'proxied': proxied
        }

        url = f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{dns_record_id}'

        response = requests.put(url, headers=headers, json=data)
        response_json = response.json()
        
        if response.status_code == 200 and response_json.get('success'):
            print(f"DNS记录更新成功！ 子域名: {subdomain}")
        else:
            print(f"DNS记录更新失败！ 子域名: {subdomain}")
            print(f"错误信息: {response_json.get('errors')}")
            print(f"响应内容: {response_json}")
    except KeyError:
        print(f"未找到子域名 {subdomain} 的 DNS 记录 ID")
    except Exception as e:
        print(f"更新 DNS 记录时发生错误: {e}")

def check_server_status(ip, ping_count=5, timeout=2):
    """
    使用 ping 检查服务器状态
    
    Args:
        ip: 要检测的IP地址
        ping_count: ping的次数
        timeout: 每次ping的超时时间(秒)
    
    Returns:
        bool: 如果服务器在线返回True,否则返回False
    """
    try:
        # 在Windows系统下使用 -n 参数,在Linux/Unix系统下使用 -c 参数
        param = '-n' if os.name == 'nt' else '-c'
        # 构建ping命令
        command = ['ping', param, str(ping_count), '-W', str(timeout), ip]
        
        # 执行ping命令
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode == 0:
            # 解析ping结果,获取成功率
            output = result.stdout.decode()
            if os.name == 'nt':
                # Windows系统下解析结果
                match = re.search(r'(\d+)% 丢失', output)
                if match:
                    loss_rate = int(match.group(1))
                    return loss_rate < 60  # 丢包率小于60%认为服务器在线
            else:
                # Linux系统下解析结果
                match = re.search(r'(\d+)% packet loss', output)
                if match:
                    loss_rate = int(match.group(1))
                    return loss_rate < 60  # 丢包率小于60%认为服务器在线
        
        return False
    except Exception as e:
        print(f"Ping检测出错: {e}")
        return False

def main():
    server_ip = ''
    backup_ip = ''
    original_ip = server_ip
    server_down = False
    using_backup_ip = False
    consecutive_failures = 0  # 连续失败次数
    consecutive_successes = 0  # 连续成功次数
    
    FAILURE_THRESHOLD = 3  # 切换到备用IP需要的连续失败次数
    SUCCESS_THRESHOLD = 2  # 切换回主IP需要的连续成功次数

    subdomains = []  # 要更新的子域名列表

    original_ip_cdn_enabled = False  # 原始 IP 的 CDN 状态
    backup_ip_cdn_enabled = True    # 备用 IP 的 CDN 状态

    while True:
        try:
            server_status = check_server_status(server_ip)
            
            if not server_down and not server_status:
                consecutive_failures += 1
                consecutive_successes = 0
                print(f"检测到服务器异常,连续失败次数: {consecutive_failures}")
                
                if consecutive_failures >= FAILURE_THRESHOLD:
                    message = f"服务器宕机(连续{consecutive_failures}次检测失败),切换到备用IP {backup_ip}"
                    print(message)
                    send_dingtalk_notification(message)
                    for subdomain in subdomains:
                        update_dns_record(subdomain, backup_ip, proxied=backup_ip_cdn_enabled)
                    using_backup_ip = True
                    server_down = True
                    
            elif server_down and server_status:
                consecutive_successes += 1
                consecutive_failures = 0
                print(f"检测到服务器恢复,连续成功次数: {consecutive_successes}")
                
                if consecutive_successes >= SUCCESS_THRESHOLD:
                    message = f"服务器已恢复(连续{consecutive_successes}次检测成功),切换回原始IP {original_ip}"
                    print(message)
                    send_dingtalk_notification(message)
                    for subdomain in subdomains:
                        update_dns_record(subdomain, original_ip, proxied=original_ip_cdn_enabled)
                    using_backup_ip = False
                    server_down = False
            else:
                # 重置计数器
                if server_status:
                    consecutive_failures = 0
                else:
                    consecutive_successes = 0

            if using_backup_ip:
                print(f"域名正在使用备用IP。CDN 状态：{'已开启' if backup_ip_cdn_enabled else '已关闭'}")
            else:
                print(f"域名正在使用原始IP。CDN 状态：{'已开启' if original_ip_cdn_enabled else '已关闭'}")

            time.sleep(60)  # 每分钟检查一次
        except Exception as e:
            error_message = f"发生未捕获的异常：{e}"
            print(error_message)
            send_dingtalk_notification(error_message)

if __name__ == "__main__":
    main()