from tkinter import *
from tkinter import scrolledtext
import requests
from bs4 import BeautifulSoup
import time
import threading
import os
from tkinterhtml import HtmlFrame

class Application(Tk):
    def __init__(self):
        super().__init__()
        self.title("XMG游戏团队")
        self.geometry("800x600")

        self.create_widgets()
        self.initialize_files()

    def create_widgets(self):
        # 公告标签和HTML框架
        self.announcement_label = Label(self, text="公告:")
        self.announcement_label.grid(row=0, column=0, sticky='w')
        self.announcement_frame = HtmlFrame(self, horizontal_scrollbar="auto")
        self.announcement_frame.grid(row=1, column=0, columnspan=4, sticky='nsew')

        # 刷新公告按钮
        self.refresh_button = Button(self, text="刷新公告", command=self.refresh_announcement)
        self.refresh_button.grid(row=0, column=1, sticky='e')

        # 玩家ID输入框和标签
        self.player_id_label = Label(self, text="输入玩家ID:")
        self.player_id_label.grid(row=2, column=0, sticky='w')
        self.player_id_entry = Entry(self, width=30)
        self.player_id_entry.grid(row=2, column=1, sticky='w')

        # 添加ID按钮
        self.add_id_button = Button(self, text="添加ID", command=self.add_player_id)
        self.add_id_button.grid(row=2, column=2, sticky='w')

        # 按钮框架
        self.button_frame = Frame(self)
        self.button_frame.grid(row=3, column=0, columnspan=4, pady=10, sticky='ew')

        # 开始领取按钮
        self.start_button = Button(self.button_frame, text="开始领取", command=self.start_retrieve)
        self.start_button.pack(side=LEFT, padx=5)

        # 停止领取按钮
        self.stop_button = Button(self.button_frame, text="停止领取", command=self.stop_retrieve)
        self.stop_button.pack(side=LEFT, padx=5)

        # 全自动托管按钮
        self.auto_button = Button(self.button_frame, text="全自动托管", command=self.open_browser)
        self.auto_button.pack(side=LEFT, padx=5)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(self, wrap=WORD, width=100, height=10)
        self.log_text.grid(row=4, column=0, columnspan=4, pady=10, sticky='nsew')

        # 界面布局调整
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)

    def initialize_files(self):
        self.create_file_if_not_exists('ids.txt', '示例玩家ID\n')
        self.create_file_if_not_exists('results.txt')

    def create_file_if_not_exists(self, filename, content=""):
        if not os.path.exists(filename):
            with open(filename, 'w') as file:
                file.write(content)

    def refresh_announcement(self):
        try:
            response = requests.get('https://xmg8.github.io/kop/')
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            announcement = soup.find("div", class_="announcement").decode_contents()
            self.announcement_frame.set_content(announcement)
        except requests.RequestException as e:
            self.log(f"获取公告失败: {e}")

    def add_player_id(self):
        player_id = self.player_id_entry.get().strip()
        if player_id:
            with open('ids.txt', 'a') as file:
                file.write(f"{player_id}\n")
            self.player_id_entry.delete(0, END)
            self.log(f"添加玩家ID: {player_id}")

    def log(self, message):
        self.log_text.insert(END, message + '\n')
        self.log_text.see(END)

    def open_browser(self):
        import webbrowser
        webbrowser.open('http://www.xmg888.top')

    def start_retrieve(self):
        self.log("开始领取任务")
        self.retrieve_thread = threading.Thread(target=self.run_script)
        self.retrieve_thread.start()

    def stop_retrieve(self):
        self.stop_retrieve_flag = True
        self.log("停止领取任务")

    def run_script(self):
        self.stop_retrieve_flag = False
        player_ids = self.read_ids('ids.txt')
        successful_ids, failed_ids = set(), set()

        self.log(f"需要执行任务的ID总数: {len(player_ids)}")

        for idx, player_id in enumerate(player_ids):
            if self.stop_retrieve_flag:
                self.log("领取任务被手动停止")
                break

            self.log(f"正在执行第 {idx + 1}/{len(player_ids)} 个任务: 玩家ID {player_id}")
            token = self.login(player_id, None)
            if not token:
                failed_ids.add(player_id)
                continue

            checkin_details = self.get_checkin_details(token, player_id)
            if not checkin_details:
                failed_ids.add(player_id)
                continue

            no_task = True
            if checkin_details and checkin_details['code'] == 1:
                for day_info in checkin_details['data']['activity_gifts_list']:
                    if day_info['status'] == 1:
                        no_task = False
                        checkin_day = int(day_info['name_language_code'].replace('第', '').replace('日', ''))
                        for attempt in range(1, 6):
                            checkin_response = self.daily_checkin(token, player_id, checkin_day)
                            if checkin_response and checkin_response['code'] == 1:
                                self.log(f"玩家 {player_id} 第{checkin_day}天签到成功")
                                successful_ids.add(player_id)
                                break
                            else:
                                self.log(f"第{checkin_day}天签到失败，重试 {attempt}/5 次")
                                time.sleep(2)
                        else:
                            self.log(f"玩家 {player_id} 第{checkin_day}天签到最终失败")
                            failed_ids.add(player_id)
                if no_task:
                    self.log(f"玩家 {player_id} 没有可领取的每日签到任务或任务已完成")
                    successful_ids.add(player_id)

            time.sleep(2)

        self.log(f"成功的ID总数: {len(successful_ids)}")
        self.log(f"失败的ID总数: {len(failed_ids)}")

    def read_ids(self, filename):
        ids = []
        with open(filename, 'r') as file:
            for line in file:
                line = line.strip()
                if line and line != '示例玩家ID':
                    ids.append(line)
        return ids

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
                    if response.status_code == 200:
                        return response.json()
                    else:
                        self.log(f"每日签到详情获取失败 玩家 {player_id}，状态码: {response.status_code}")
            except requests.RequestException as e:
                self.log(f"每日签到详情获取失败 玩家 {player_id}，重试 {attempt + 1}/3 次: {e}")
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
                    if response.status_code == 200:
                        return response.json()
                    else:
                        self.log(f"每日签到请求 玩家 {player_id} 第{checkin_day}天失败，状态码: {response.status_code}")
            except requests.RequestException as e:
                self.log(f"每日签到请求 玩家 {player_id} 第{checkin_day}天失败，重试 {attempt + 1}/3 次: {e}")
                time.sleep(2)
        return None

if __name__ == "__main__":
    app = Application()
    app.mainloop()
