import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox
import requests
import threading
import webbrowser
import time
import random
import psutil
import os
from requests.exceptions import ConnectionError, Timeout, SSLError
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from tkhtmlview import HTMLLabel

# 忽略SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

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

# 读取游戏ID和密码列表
def read_ids_and_passwords(filename):
    ids_and_passwords = []
    try:
        with open(filename, 'r', encoding='utf-8') as file:
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
        with open(filename, 'r', encoding='utf-8') as file:
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
                if response.status_code == 200 and 'Authorization' in response.headers:
                    return response.headers['Authorization']
                else:
                    print(f"登录失败，状态码: {response.status_code}, 响应: {response.text}")
        except (ConnectionError, Timeout, SSLError) as e:
            if isinstance(e, SSLError):
                proxies = None
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
                return response.json() if response.status_code == 200 else None
        except (ConnectionError, Timeout, SSLError) as e:
            if isinstance(e, SSLError):
                proxies = None
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
                return response.json() if response.status_code == 200 else None
        except (ConnectionError, Timeout, SSLError) as e:
            if isinstance(e, SSLError):
                proxies = None
            time.sleep(2)  # 等待一段时间后重试
    return None

# 记录失败的IP地址
def log_failed_ip(ip):
    with open('ip.txt', 'a', encoding='utf-8') as file:
        file.write(f"{datetime.now()} 失败的IP: {ip}\n")

# 打印系统资源使用情况
def print_system_usage():
    process = psutil.Process()
    mem_info = process.memory_info()
    cpu_usage = psutil.cpu_percent(interval=1)
    return f"当前内存使用: {mem_info.rss / 1024 ** 2:.2f} MB\n当前CPU使用: {cpu_usage:.2f} %\n"

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XMG游戏团队")
        self.geometry("600x600")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.announcement_html = HTMLLabel(self, html="", width=100, height=10)
        self.announcement_html.pack()

        self.refresh_button = tk.Button(self, text="刷新公告", command=self.refresh_announcement)
        self.refresh_button.pack()

        self.id_entry = tk.Entry(self)
        self.id_entry.pack()

        self.add_id_button = tk.Button(self, text="添加ID", command=self.add_id)
        self.add_id_button.pack()

        self.start_button = tk.Button(self, text="开始领取", command=self.start_retrieve)
        self.start_button.pack()

        self.stop_button = tk.Button(self, text="停止领取", command=self.stop_retrieve)
        self.stop_button.pack()

        self.auto_manage_button = tk.Button(self, text="全自动托管", command=self.auto_manage)
        self.auto_manage_button.pack()

        self.log_output = scrolledtext.ScrolledText(self, width=100, height=20)
        self.log_output.pack()

        self.retrieve_thread = None
        self.stop_event = threading.Event()

    def refresh_announcement(self):
        url = 'https://xmg8.github.io/kop/announcement.html'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            announcement = response.text.strip()
            self.announcement_html.set_html(announcement)
        except Exception as e:
            self.log(f"获取公告失败: {e}")

    def add_id(self):
        player_id = self.id_entry.get()
        if player_id:
            with open('ids.txt', 'a', encoding='utf-8') as file:
                file.write(f"{player_id}\n")
            self.id_entry.delete(0, tk.END)
            self.log(f"添加ID: {player_id}")

    def start_retrieve(self):
        if self.retrieve_thread and self.retrieve_thread.is_alive():
            messagebox.showwarning("警告", "任务正在进行中")
            return
        self.stop_event.clear()
        self.retrieve_thread = threading.Thread(target=self.run_script)
        self.retrieve_thread.start()

    def stop_retrieve(self):
        self.stop_event.set()

    def auto_manage(self):
        webbrowser.open("http://www.xmg888.top")

    def run_script(self):
        initialize_files()
        
        ids_and_passwords = read_ids_and_passwords('ids.txt')
        unique_ids_and_passwords = list(set(ids_and_passwords))
        successful_ids, failed_ids = read_results('results.txt')

        # 过滤掉已经成功签到的ID
        ids_to_run = [(id, pwd) for id, pwd in unique_ids_and_passwords if id not in successful_ids]

        self.log(f"开始领取任务\n需要执行任务的ID总数: {len(ids_to_run)}")

        for idx, (player_id, password) in enumerate(ids_to_run):
            if self.stop_event.is_set():
                self.log("停止领取任务")
                break

            current_task_number = idx + 1
            self.log(f"正在执行第 {current_task_number}/{len(ids_to_run)} 个任务: 玩家ID {player_id}")

            token = login(player_id, password, None)
            if not token:
                self.log(f"玩家 {player_id} 登录失败，停止执行该ID任务")
                failed_ids.add(player_id)
                continue

            checkin_details = get_checkin_details(token, player_id, None)
            if not checkin_details:
                self.log(f"玩家 {player_id} 获取每日签到详情失败")
                failed_ids.add(player_id)
                continue

            no_task = True
            if checkin_details and checkin_details['code'] == 1:
                for day_info in checkin_details['data']['activity_gifts_list']:
                    if day_info['status'] == 1:  # 检查是否可以领取
                        no_task = False
                        checkin_day = int(day_info['name_language_code'].replace('第', '').replace('日', ''))
                        for attempt in range(1, 4):
                            checkin_response = daily_checkin(token, player_id, checkin_day, None)
                            if checkin_response and checkin_response['code'] == 1:
                                self.log(f"玩家 {player_id} 第{checkin_day}天签到成功")
                                successful_ids.add(player_id)
                                break
                            else:
                                self.log(f"玩家 {player_id} 第{checkin_day}天签到失败，重试 {attempt}/3 次")
                                time.sleep(2)
                        else:
                            self.log(f"玩家 {player_id} 第{checkin_day}天签到最终失败")
                            failed_ids.add(player_id)
            if no_task:
                self.log(f"玩家 {player_id} 没有可领取的每日签到任务或任务已完成")
                successful_ids.add(player_id)

            # 添加延迟，模拟人类操作
            time.sleep(random.randint(3, 6))

        self.log(f"成功的ID总数: {len(successful_ids)}\n失败的ID总数: {len(failed_ids)}")

    def log(self, message):
        self.log_output.insert(tk.END, f"{message}\n")
        self.log_output.see(tk.END)

    def on_closing(self):
        if messagebox.askokcancel("退出", "确定退出吗?"):
            self.stop_event.set()
            self.destroy()

if __name__ == "__main__":
    app = Application()
    app.refresh_announcement()
    app.mainloop()
