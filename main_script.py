import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import threading
import webbrowser
from datetime import datetime
import os
import random
import time
from bs4 import BeautifulSoup

# 创建文件（如果不存在）
def create_file_if_not_exists(filename, content=""):
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(content)

# 初始化所需文件
def initialize_files():
    create_file_if_not_exists('ids.txt', '')
    create_file_if_not_exists('results.txt')
    create_file_if_not_exists('ip.txt')

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XMG游戏团队")
        self.geometry("700x600")

        # 公告
        self.announcement_label = tk.Label(self, text="公告:", font=("Arial", 12))
        self.announcement_label.grid(row=0, column=0, sticky="w")

        self.announcement_text = scrolledtext.ScrolledText(self, width=80, height=10, wrap=tk.WORD)
        self.announcement_text.grid(row=1, column=0, columnspan=5, padx=10, pady=5)
        self.update_announcement()

        # 输入框和按钮
        self.id_label = tk.Label(self, text="输入玩家ID:")
        self.id_label.grid(row=2, column=0, pady=5)

        self.id_entry = tk.Entry(self)
        self.id_entry.grid(row=2, column=1, pady=5)

        self.add_button = tk.Button(self, text="添加ID", command=self.add_id)
        self.add_button.grid(row=2, column=2, pady=5)

        self.start_button = tk.Button(self, text="开始领取", command=self.start_retrieve)
        self.start_button.grid(row=2, column=3, pady=5)

        self.stop_button = tk.Button(self, text="停止领取", command=self.stop_retrieve)
        self.stop_button.grid(row=2, column=4, pady=5)

        self.auto_button = tk.Button(self, text="全自动托管", command=self.open_auto_manage)
        self.auto_button.grid(row=3, column=2, pady=5)

        # 日志框
        self.log_text = scrolledtext.ScrolledText(self, width=80, height=15, wrap=tk.WORD)
        self.log_text.grid(row=4, column=0, columnspan=5, padx=10, pady=5)

        self.running = False

        initialize_files()

    def update_announcement(self):
        try:
            response = requests.get('https://xmg8.github.io/kop/', timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            announcement = soup.find('div', class_='announcement').prettify()
            self.announcement_text.delete(1.0, tk.END)
            self.announcement_text.insert(tk.END, announcement)
        except Exception as e:
            self.announcement_text.delete(1.0, tk.END)
            self.announcement_text.insert(tk.END, f"获取公告失败: {e}")

    def add_id(self):
        player_id = self.id_entry.get().strip()
        if player_id:
            with open('ids.txt', 'a', encoding='utf-8') as file:
                file.write(f"{player_id}\n")
            self.log(f"添加玩家ID: {player_id}")
            self.id_entry.delete(0, tk.END)

    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def start_retrieve(self):
        if not self.running:
            self.running = True
            self.log("开始领取任务")
            threading.Thread(target=self.run_script).start()

    def stop_retrieve(self):
        self.running = False
        self.log("停止领取任务")

    def open_auto_manage(self):
        webbrowser.open('http://www.xmg888.top')

    def run_script(self):
        ids_and_passwords = self.read_ids_and_passwords('ids.txt')
        unique_ids_and_passwords = list(set(ids_and_passwords))
        successful_ids, failed_ids = self.read_results('results.txt')

        # 过滤掉已经成功签到的ID
        ids_to_run = [(id, pwd) for id, pwd in unique_ids_and_passwords if id not in successful_ids]

        self.log(f"读取到的ID总数: {len(unique_ids_and_passwords)}")
        self.log(f"成功的ID总数: {len(successful_ids)}")
        self.log(f"失败的ID总数: {len(failed_ids)}")
        self.log(f"需要执行任务的ID总数: {len(ids_to_run)}")

        for idx, (player_id, password) in enumerate(ids_to_run):
            if not self.running:
                break
            current_task_number = idx + 1
            self.log(f"正在执行第 {current_task_number}/{len(ids_to_run)} 个任务: 玩家ID {player_id}")

            token = self.login(player_id, password)
            if not token:
                self.log(f"玩家 {player_id} 登录失败")
                failed_ids.add(player_id)
                continue

            checkin_details = self.get_checkin_details(token, player_id)
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
                        for attempt in range(1, 6):
                            checkin_response = self.daily_checkin(token, player_id, checkin_day)
                            if checkin_response and checkin_response['code'] == 1:
                                self.log(f"玩家 {player_id} 第{checkin_day}天签到成功")
                                successful_ids.add(player_id)
                                break
                            else:
                                self.log(f"第{checkin_day}天签到失败，重试 {attempt}/5 次: {checkin_response}")
                                time.sleep(2)
                        else:
                            self.log(f"玩家 {player_id} 第{checkin_day}天签到最终失败: {checkin_response}")
                            failed_ids.add(player_id)
            if no_task:
                self.log(f"玩家 {player_id} 没有可领取的每日签到任务或任务已完成")
                successful_ids.add(player_id)

            # 添加延迟，模拟人类操作
            time.sleep(random.randint(3, 6))

        self.log(f"成功的ID总数: {len(successful_ids)}")
        self.log(f"失败的ID总数: {len(failed_ids)}")
        self.log("停止领取任务")

    def read_ids_and_passwords(self, filename):
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
            self.log(f"文件 {filename} 未找到")
        return ids_and_passwords

    def read_results(self, filename):
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
                        if "签到成功" in line or ("第" in line and "天签到成功" in line) or "没有可领取的每日签到任务或任务已完成" in line:
                            successful_ids.add(player_id)
                        else:
                            failed_ids.add(player_id)
        except FileNotFoundError:
            self.log(f"文件 {filename} 未找到")
        return successful_ids, failed_ids

    def login(self, player_id, password):
        url = 'https://ls.store.koppay.net/api/v2/store/login/player'
        payload = {'player_id': player_id, 'site_id': 22}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        if password:
            payload['password'] = password

        for attempt in range(3):
            try:
                with requests.Session() as session:
                    response = session.post(url, json=payload, headers=headers, timeout=10)
                    if response.status_code == 200 and 'Authorization' in response.headers:
                        return response.headers['Authorization']
                    else:
                        self.log(f"玩家 {player_id} 登录失败，状态码: {response.status_code}, 响应: {response.text}")
            except requests.RequestException as e:
                self.log(f"玩家 {player_id} 登录请求失败，重试 {attempt + 1}/3 次: {e}")
                time.sleep(2)
        return None

    def get_checkin_details(self, token, player_id):
        url = f'https://ls.store.koppay.net/api/v2/store/sale/biz/get/checkin/details?project_id=15&player_id={player_id}'
        headers = {
            'Authorization': token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        for attempt in range(3):
            try:
                with requests.Session() as session:
                    response = session.get(url, headers=headers, timeout=10)
                    return response.json() if response.status_code == 200 else None
            except requests.RequestException as e:
                self.log(f"获取每日签到详情失败，重试 {attempt + 1}/3 次: {e}")
                time.sleep(2)
        return None

    def daily_checkin(self, token, player_id, checkin_day):
        url = 'https://ls.store.koppay.net/api/v2/store/sale/biz/add/checkin/create'
        headers = {
            'Authorization': token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        payload = {'project_id': 15, 'player_id': player_id, 'checkin_day': checkin_day}

        for attempt in range(3):
            try:
                with requests.Session() as session:
                    response = session.post(url, json=payload, headers=headers, timeout=10)
                    return response.json() if response.status_code == 200 else None
            except requests.RequestException as e:
                self.log(f"每日签到失败，重试 {attempt + 1}/3 次: {e}")
                time.sleep(2)
        return None

if __name__ == '__main__':
    app = Application()
    app.mainloop()
