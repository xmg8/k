from datetime import datetime
import requests
import random
import time
import psutil
import os
from requests.exceptions import ConnectionError, Timeout, SSLError
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 忽略SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# 设置代理API URL
proxy_api_url = 'https://get.ip.sgxz.cn/get/ip?pt=22&num=1&gt=0&isp=2&port=1&time=5&type=1&pack=3417&ts=0&lb=1&clb=&sp=0&csp=&distinct=2&aw=0&at=1&regions=610000,420000,430000,130000,510000,370000,440000'

# 创建文件（如果不存在）
def create_file_if_not_exists(filename, content=""):
    if not os.path.exists(filename):
        with open(filename, 'w') as file:
            file.write(content)

# 初始化所需文件
def initialize_files():
    create_file_if_not_exists('ids.txt', '示例玩家ID\n')
    create_file_if_not_exists('results.txt')
    create_file_if_not_exists('ip.txt')

# 获取代理IP
def get_proxy():
    try:
        response = requests.get(proxy_api_url, timeout=10)
        response.raise_for_status()
        proxy_ip_port = response.text.strip()
        ip, port = proxy_ip_port.split(":")
        return {
            'http': f"http://{ip}:{port}",
            'https': f"https://{ip}:{port}"
        }
    except Exception as e:
        print(f"获取代理IP失败: {e}")
        return None

# 检测代理IP是否可用
def is_proxy_working(proxy):
    test_url = 'https://httpbin.org/ip'
    try:
        response = requests.get(test_url, proxies=proxy, timeout=5, verify=False)
        if response.status_code == 200:
            print(f"使用代理IP {proxy['http']} 请求成功，返回IP: {response.json()['origin']}")
            return True
    except Exception as e:
        print(f"代理不可用: {e}")
    return False

# 读取游戏ID和密码列表
def read_ids_and_passwords(filename):
    ids_and_passwords = []
    try:
        with open(filename, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) == 1:
                    ids_and_passwords.append((parts[0], None))  # 只有ID，没有密码
                elif len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 6:
                    ids_and_passwords.append((parts[0], parts[1]))  # ID和6位数字密码
    except FileNotFoundError:
        print(f"文件 {filename} 未找到")
    return ids_and_passwords

# 读取结果文件并解析签到结果
def read_results(filename):
    successful_ids = set()
    failed_ids = set()
    current_date = datetime.now().strftime('%Y-%m-%d')
    try:
        with open(filename, 'r') as file:
            for line in file.readlines():
                parts = line.split()
                if len(parts) < 4:
                    continue
                result_date = parts[0].split('T')[0]
                player_id = parts[3]  # 假设ID总是位于第四个位置
                if result_date == current_date:
                    if "签到成功" in line or ("第" in line and "天签到成功" in line) or "没有可领取的每日签到任务或任务已完成" in line or "重试没有可领取的每日签到任务或任务已完成" in line:
                        successful_ids.add(player_id)
                    else:
                        failed_ids.add(player_id)
    except FileNotFoundError:
        print(f"文件 {filename} 未找到")

    print(f"成功的ID列表: {successful_ids}")
    print(f"失败的ID列表: {failed_ids}")

    return successful_ids, failed_ids

# 登录请求并获取token
def login(player_id, password, proxies, max_retries=3):
    url = 'https://ls.store.koppay.net/api/v2/store/login/player'
    payload = {'player_id': player_id, 'site_id': 22}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    if password:
        payload['password'] = password

    for attempt in range(max_retries):
        try:
            with requests.Session() as session:
                response = session.post(url, json=payload, headers=headers, proxies=proxies, verify=False, timeout=10)
                print(f"玩家 {player_id} 登录响应: {response.status_code}")
                if response.status_code == 200 and 'Authorization' in response.headers:
                    return response.headers['Authorization']
                else:
                    print(f"登录失败，状态码: {response.status_code}, 响应: {response.text}")
        except (ConnectionError, Timeout, SSLError) as e:
            print(f"登录请求失败，重试 {attempt + 1}/{max_retries} 次: {e}")
            if isinstance(e, SSLError):
                # 更换代理
                proxies = get_proxy()
                while proxies and not is_proxy_working(proxies):
                    proxies = get_proxy()
            time.sleep(2)  # 等待一段时间后重试
    return None

# 获取每日签到详情
def get_checkin_details(token, player_id, proxies, max_retries=3):
    url = f'https://ls.store.koppay.net/api/v2/store/sale/biz/get/checkin/details?project_id=15&player_id={player_id}'
    headers = {
        'Authorization': token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for attempt in range(max_retries):
        try:
            with requests.Session() as session:
                response = session.get(url, headers=headers, proxies=proxies, verify=False, timeout=10)
                print(f"每日签到详情获取 {player_id}: {response.status_code}")
                return response.json() if response.status_code == 200 else None
        except (ConnectionError, Timeout, SSLError) as e:
            print(f"获取每日签到详情失败，重试 {attempt + 1}/{max_retries} 次: {e}")
            if isinstance(e, SSLError):
                # 更换代理
                proxies = get_proxy()
                while proxies and not is_proxy_working(proxies):
                    proxies = get_proxy()
            time.sleep(2)  # 等待一段时间后重试
    return None

# 执行每日签到
def daily_checkin(token, player_id, checkin_day, proxies, max_retries=3):
    url = 'https://ls.store.koppay.net/api/v2/store/sale/biz/add/checkin/create'
    headers = {
        'Authorization': token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    payload = {'project_id': 15, 'player_id': player_id, 'checkin_day': checkin_day}

    for attempt in range(max_retries):
        try:
            with requests.Session() as session:
                response = session.post(url, json=payload, headers=headers, proxies=proxies, verify=False, timeout=10)
                print(f"每日签到响应 玩家 {player_id}, 第 {checkin_day} 天: {response.status_code}, {response.text}")
                return response.json() if response.status_code == 200 else None
        except (ConnectionError, Timeout, SSLError) as e:
            print(f"每日签到失败，重试 {attempt + 1}/{max_retries} 次: {e}")
            if isinstance(e, SSLError):
                # 更换代理
                proxies = get_proxy()
                while proxies and not is_proxy_working(proxies):
                    proxies = get_proxy()
            time.sleep(2)  # 等待一段时间后重试
    return None

# 记录失败的IP地址
def log_failed_ip(ip):
    with open('ip.txt', 'a') as file:
        file.write(f"{datetime.now()} 失败的IP: {ip}\n")

# 打印系统资源使用情况
def print_system_usage():
    process = psutil.Process()
    mem_info = process.memory_info()
    cpu_usage = psutil.cpu_percent(interval=1)

    print(f"当前内存使用: {mem_info.rss / 1024 ** 2:.2f} MB")
    print(f"当前CPU使用: {cpu_usage:.2f} %")

# 主函数
def main():
    initialize_files()
    
    ids_and_passwords = read_ids_and_passwords('ids.txt')
    unique_ids_and_passwords = list(set(ids_and_passwords))
    successful_ids, failed_ids = read_results('results.txt')

    # 过滤掉已经成功签到的ID
    ids_to_run = [(id, pwd) for id, pwd in unique_ids_and_passwords if id not in successful_ids]

    print(f"读取到的ID总数: {len(unique_ids_and_passwords)}")
    print(f"成功的ID总数: {len(successful_ids)}")
    print(f"失败的ID总数: {len(failed_ids)}")
    print(f"需要执行任务的ID总数: {len(ids_to_run)}")
    print(f"需要执行任务的ID列表: {ids_to_run}")

    proxies = get_proxy()
    while proxies and not is_proxy_working(proxies):
        proxies = get_proxy()

    for idx, (player_id, password) in enumerate(ids_to_run):
        current_task_number = idx + 1
        print(f"正在执行第 {current_task_number}/{len(ids_to_run)} 个任务: 玩家ID {player_id}")
        print_system_usage()  # 打印系统资源使用情况

        token = login(player_id, password, proxies)
        if not token:
            proxy_ip = proxies['http'].split('//')[1].split(':')[0]
            log_failed_ip(proxy_ip)
            with open('results.txt', 'a') as file:
                file.write(f"{datetime.now()} 玩家 {player_id} 登录失败\n")
            failed_ids.add(player_id)
            continue

        checkin_details = get_checkin_details(token, player_id, proxies)
        if not checkin_details:
            with open('results.txt', 'a') as file:
                file.write(f"{datetime.now()} 玩家 {player_id} 获取每日签到详情失败\n")
            failed_ids.add(player_id)
            continue

        no_task = True
        if checkin_details and checkin_details['code'] == 1:
            for day_info in checkin_details['data']['activity_gifts_list']:
                if day_info['status'] == 1:  # 检查是否可以领取
                    no_task = False
                    checkin_day = int(day_info['name_language_code'].replace('第', '').replace('日', ''))
                    for attempt in range(1, 6):
                        checkin_response = daily_checkin(token, player_id, checkin_day, proxies)
                        if checkin_response and checkin_response['code'] == 1:
                            with open('results.txt', 'a') as file:
                                file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到成功\n")
                            successful_ids.add(player_id)
                            break
                        else:
                            print(f"第{checkin_day}天签到失败，重试 {attempt}/5 次: {checkin_response}")
                            time.sleep(2)
                    else:
                        with open('results.txt', 'a') as file:
                            file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到最终失败: {checkin_response}\n")
                        failed_ids.add(player_id)
        if no_task:
            with open('results.txt', 'a') as file:
                file.write(f"{datetime.now()} 玩家 {player_id} 没有可领取的每日签到任务或任务已完成\n")
            successful_ids.add(player_id)

        # 添加延迟，模拟人类操作
        time.sleep(random.randint(3, 6))

        # 每三个ID重新获取代理
        if (current_task_number) % 3 == 0:
            proxies = get_proxy()
            while proxies and not is_proxy_working(proxies):
                proxies = get_proxy()

if __name__ == '__main__':
    main()
