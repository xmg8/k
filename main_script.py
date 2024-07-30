import tkinter as tk
from tkinter import messagebox
import threading
import requests
import random
import time
import os

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XMG游戏团队")

        # 公告显示区域
        self.announcement_label = tk.Label(self, text="公告:")
        self.announcement_label.grid(row=0, column=0, sticky='w')
        self.announcement_text = tk.Text(self, wrap='word', width=50, height=10)
        self.announcement_text.grid(row=1, column=0, columnspan=5, padx=5, pady=5)
        self.refresh_announcement()

        # 输入框和按钮
        self.id_entry_label = tk.Label(self, text="输入玩家ID:")
        self.id_entry_label.grid(row=2, column=0)
        self.id_entry = tk.Entry(self, width=20)
        self.id_entry.grid(row=2, column=1)

        self.add_button = tk.Button(self, text="添加ID", command=self.add_id)
        self.add_button.grid(row=2, column=2)

        self.start_button = tk.Button(self, text="开始领取", command=self.start_retrieve)
        self.start_button.grid(row=2, column=3)

        self.stop_button = tk.Button(self, text="停止领取", command=self.stop_retrieve)
        self.stop_button.grid(row=2, column=4)

        self.auto_button = tk.Button(self, text="全自动托管", command=self.auto_manage)
        self.auto_button.grid(row=3, column=0, columnspan=5)

        # 日志显示区域
        self.log_output = tk.Text(self, wrap='word', width=70, height=15)
        self.log_output.grid(row=4, column=0, columnspan=5, padx=5, pady=5)

        self.stop_event = threading.Event()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def refresh_announcement(self):
        try:
            response = requests.get('https://xmg8.github.io/kop/')
            response.raise_for_status()
            html_content = response.text
            start_idx = html_content.find('<body>') + len('<body>')
            end_idx = html_content.find('</body>')
            body_content = html_content[start_idx:end_idx].strip()

            self.announcement_text.delete('1.0', tk.END)
            self.announcement_text.insert(tk.END, body_content)
        except Exception as e:
            self.log(f"获取公告失败: {e}")

    def add_id(self):
        player_id = self.id_entry.get().strip()
        if player_id:
            with open('ids.txt', 'a') as file:
                file.write(f"{player_id}\n")
            self.log(f"添加玩家ID: {player_id}")
            self.id_entry.delete(0, tk.END)
        else:
            self.log("请输入玩家ID")

    def start_retrieve(self):
        self.stop_event.clear()
        self.log("开始领取任务")
        threading.Thread(target=self.run_script).start()

    def stop_retrieve(self):
        self.stop_event.set()
        self.log("停止领取任务")

    def auto_manage(self):
        import webbrowser
        webbrowser.open('http://www.xmg888.top')

    def run_script(self):
        if not os.path.exists('ids.txt'):
            self.log("ID文件不存在，请添加玩家ID")
            return
        
        ids_and_passwords = read_ids_and_passwords('ids.txt')
        unique_ids_and_passwords = list(set(ids_and_passwords))
        successful_ids, failed_ids = read_results('results.txt')

        ids_to_run = [(id, pwd) for id, pwd in unique_ids_and_passwords if id not in successful_ids]

        self.log(f"需要执行任务的ID总数: {len(ids_to_run)}")

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
                    if day_info['status'] == 1: 
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

            time.sleep(random.randint(3, 6))

        self.log(f"成功的ID总数: {len(successful_ids)}\n失败的ID总数: {len(failed_ids)}")

    def log(self, message):
        self.log_output.insert(tk.END, f"{message}\n")
        self.log_output.see(tk.END)

    def on_closing(self):
        if messagebox.askokcancel("退出", "确定退出吗?"):
            self.stop_event.set()
            self.destroy()

def read_ids_and_passwords(filename):
    ids_and_passwords = []
    try:
        with open(filename, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) == 1:
                    ids_and_passwords.append((parts[0], None)) 
                elif len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 6:
                    ids_and_passwords.append((parts[0], parts[1])) 
    except FileNotFoundError:
        print(f"文件 {filename} 未找到")
    return ids_and_passwords

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
                player_id = parts[3] 
                if result_date == current_date:
                    if "签到成功" in line or ("第" in line and "天签到成功" in line) or "没有可领取的每日签到任务或任务已完成" in line or "重试没有可领取的每日签到任务或任务已完成" in line:
                        successful_ids.add(player_id)
                    else:
                        failed_ids.add(player_id)
    except FileNotFoundError:
        print(f"文件 {filename} 未找到")

    return successful_ids, failed_ids

def login(player_id, password, proxies):
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
                response = session.post(url, json=payload, headers=headers, proxies=proxies, verify=False, timeout=10)
                if response.status_code == 200 and 'Authorization' in response.headers:
                    return response.headers['Authorization']
        except Exception as e:
            time.sleep(2)  
    return None

def get_checkin_details(token, player_id, proxies):
    url = f'https://ls.store.koppay.net/api/v2/store/sale/biz/get/checkin/details?project_id=15&player_id={player_id}'
    headers = {
        'Authorization': token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for attempt in range(3):
        try:
            with requests.Session() as session:
                response = session.get(url, headers=headers, proxies=proxies, verify=False, timeout=10)
                return response.json() if response.status_code == 200 else None
        except Exception as e:
            time.sleep(2)
    return None

def daily_checkin(token, player_id, checkin_day, proxies):
    url = 'https://ls.store.koppay.net/api/v2/store/sale/biz/add/checkin/create'
    headers = {
        'Authorization': token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    payload = {'project_id': 15, 'player_id': player_id, 'checkin_day': checkin_day}

    for attempt in range(3):
        try:
            with requests.Session() as session:
                response = session.post(url, json=payload, headers=headers, proxies=proxies, verify=False, timeout=10)
                return response.json() if response.status_code == 200 else None
        except Exception as e:
            time.sleep(2)
    return None

if __name__ == '__main__':
    app = Application()
    app.mainloop()
