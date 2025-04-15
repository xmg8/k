import sys
import requests
import time
from urllib.parse import urlencode
import os
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon


# 配置项
API_ACCOUNT = "011474da7ce8c4d4fe58ad3eb95595fba150872eaf35cc85d692b2b209ac61c3"
API_PASSWORD = "2128c8ba18eba394cbfb99c6c906a9b5199d9f94cd825fbcd30c41a0745281e3"
PROJECT_ID = "78478"
SERVERS = [
    "https://api.haozhuma.com",
    "https://api.haozhuma.cn",
    "https://api.haozhuyun.com",
    "https://api.haozhuyun.cn"
]

# 全局变量
token = None
phone_number = None
server = None
TOKEN_FILE = "token.txt"

# 定义请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}


def read_token():
    """从文件中读取令牌"""
    global token, server
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token = f.read().strip()
                if token:
                    # 尝试从已有的服务器列表中获取可用服务器
                    for s in SERVERS:
                        try:
                            # 可以使用一个轻量级的接口来验证服务器是否可用，这里假设用 getSummary 接口
                            url = f"{s}/sms/?api=getSummary&token={token}"
                            response = requests.get(url, headers=headers, timeout=10)
                            response.raise_for_status()
                            data = response.json()
                            if data.get("code") == 0:
                                print("从文件中读取到令牌:", token)
                                print(f"使用服务器：{s}")
                                server = s
                                return True
                        except requests.exceptions.RequestException:
                            continue
        except Exception as e:
            print(f"读取令牌文件时出错: {e}")
    return False


def save_token():
    """将令牌保存到文件中"""
    global token
    try:
        with open(TOKEN_FILE, 'w') as f:
            f.write(token)
        print("令牌已保存到文件:", TOKEN_FILE)
    except Exception as e:
        print(f"保存令牌到文件时出错: {e}")


def try_login():
    """使用API账号密码登录，返回第一个可用的服务器地址和token"""
    global server, token
    for s in SERVERS:
        login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
        try:
            response = requests.get(login_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            print(f"登录请求响应内容：{data}")
            if data.get("code") == 0:
                print(f"登录成功，使用服务器：{s}")
                server = s
                token = data["token"]
                save_token()
                return
            else:
                print(f"服务器 {s} 登录失败：{data.get('msg', '未知错误')}")
        except requests.exceptions.RequestException as e:
            print(f"服务器 {s} 连接失败：{str(e)}")
    raise Exception("所有服务器登录尝试失败")


def get_balance():
    """获取账户余额（接口不变，依赖token）"""
    url = f"{server}/sms/?api=getSummary&token={token}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        print(f"获取余额请求响应内容：{data}")
        if data.get("code") == 0:
            balance = data["money"]
            print(f"账户余额：{balance} 元")
            return balance
        elif data.get("code") == "令牌过期错误码":  # 需替换为实际的令牌过期错误码
            print("令牌过期，重新获取令牌")
            try_login()
            return get_balance()
        else:
            print(f"获取余额失败：{data.get('msg', '未知错误')}")
    except Exception as e:
        print(f"获取余额异常：{str(e)}")


def get_phone_number():
    """获取手机号码（接口不变）"""
    global phone_number
    url = f"{server}/sms/?api=getPhone&token={token}&sid={PROJECT_ID}"
    while True:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            print(f"获取手机号码请求响应内容：{data}")
            if data.get("code") == "0":
                phone_number = data["phone"]
                print(f"获取手机号码成功：{phone_number}")
                return phone_number
            elif data.get("code") == "令牌过期错误码":  # 需替换为实际的令牌过期错误码
                print("令牌过期，重新获取令牌")
                try_login()
                url = f"{server}/sms/?api=getPhone&token={token}&sid={PROJECT_ID}"
            else:
                print(f"获取手机号失败：{data.get('msg', '未知错误')}")
        except Exception as e:
            print(f"获取手机号异常：{str(e)}")
        time.sleep(2)  # 每次请求延迟2秒


def wait_for_verification_code(timeout=120):
    """使用新接口 getMessage 获取验证码（请求方式：GET/POST，需根据实际调整）"""
    global phone_number
    start_time = time.time()
    while time.time() - start_time < timeout:
        params = {
            "api": "getMessage",
            "token": token,
            "sid": PROJECT_ID,
            "phone": phone_number
        }
        url = f"{server}/sms/?{urlencode(params)}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            print(f"获取验证码请求响应内容：{data}")
            if data.get("code") == "0":
                verification_code = data.get("yzm")
                if verification_code:
                    print(f"获取验证码成功：{verification_code}")
                    return verification_code
                else:
                    print("验证码内容为空，继续等待...")
            elif data.get("code") == "令牌过期错误码":  # 需替换为实际的令牌过期错误码
                print("令牌过期，重新获取令牌")
                try_login()
            else:
                print(f"获取验证码失败：{data.get('msg', '未知错误')}")
        except Exception as e:
            print(f"获取验证码异常：{str(e)}")
        time.sleep(5)
    print("验证码获取超时，请重试")
    blacklist_phone()
    return None


def blacklist_phone():
    """将手机号码加入黑名单"""
    global phone_number
    url = f"{server}/sms/?api=addBlacklist&token={token}&sid={PROJECT_ID}&phone={phone_number}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        print(f"拉黑手机号码请求响应内容：{data}")
        if data.get("code") == "0":
            print(f"手机号码 {phone_number} 已成功拉黑")
        else:
            print(f"拉黑手机号码失败：{data.get('msg', '未知错误')}")
    except Exception as e:
        print(f"拉黑手机号码异常：{str(e)}")


class GetPhoneThread(QThread):
    phone_signal = pyqtSignal(str)

    def run(self):
        global phone_number
        phone = get_phone_number()
        if phone:
            phone_number = phone
            self.phone_signal.emit(phone)


class GetCodeThread(QThread):
    code_signal = pyqtSignal(str)

    def run(self):
        code = wait_for_verification_code()
        if code:
            self.code_signal.emit(code)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.init_token()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 设置窗口图标
        self.setWindowIcon(QIcon('icon.png'))

        # 获取手机号按钮
        self.get_phone_button = QPushButton('获取手机号')
        self.get_phone_button.clicked.connect(self.get_phone)
        self.get_phone_button.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        layout.addWidget(self.get_phone_button)

        # 复制手机号按钮
        self.copy_phone_button = QPushButton('复制手机号码')
        self.copy_phone_button.clicked.connect(self.copy_phone)
        self.copy_phone_button.setEnabled(False)
        self.copy_phone_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        layout.addWidget(self.copy_phone_button)

        # 手机号码和验证码显示
        info_layout = QHBoxLayout()
        self.phone_label = QLabel('手机号码: ')
        self.phone_label.setStyleSheet("font-size: 16px;")
        info_layout.addWidget(self.phone_label)
        self.code_label = QLabel('验证码: ')
        self.code_label.setStyleSheet("font-size: 16px;")
        info_layout.addWidget(self.code_label)
        layout.addLayout(info_layout)

        # 获取验证码按钮
        self.get_code_button = QPushButton('获取验证码')
        self.get_code_button.clicked.connect(self.get_code)
        self.get_code_button.setEnabled(False)
        self.get_code_button.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        layout.addWidget(self.get_code_button)

        # 拉黑手机号码按钮
        self.blacklist_button = QPushButton('拉黑手机号码')
        self.blacklist_button.clicked.connect(self.blacklist)
        self.blacklist_button.setEnabled(False)
        self.blacklist_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        layout.addWidget(self.blacklist_button)

        self.setLayout(layout)
        self.setWindowTitle('短信验证码获取工具')
        self.setGeometry(300, 300, 400, 300)
        self.setStyleSheet("background-color: #f8f9fa;")
        self.show()

    def init_token(self):
        global token
        if not read_token():
            try:
                try_login()
            except Exception as e:
                QMessageBox.critical(self, '错误', f'登录失败：{str(e)}')
                sys.exit(1)
        get_balance()

    def get_phone(self):
        self.get_phone_thread = GetPhoneThread()
        self.get_phone_thread.phone_signal.connect(self.show_phone)
        self.get_phone_thread.start()
        self.get_phone_button.setEnabled(False)

    def show_phone(self, phone):
        self.phone_label.setText(f'手机号码: {phone}')
        self.copy_phone_button.setEnabled(True)
        self.get_code_button.setEnabled(True)
        self.get_phone_button.setEnabled(True)

    def copy_phone(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(phone_number)
        QMessageBox.information(self, '提示', '手机号码已复制到剪贴板')

    def get_code(self):
        self.get_code_thread = GetCodeThread()
        self.get_code_thread.code_signal.connect(self.show_code)
        self.get_code_thread.start()
        self.get_code_button.setEnabled(False)
        self.blacklist_button.setEnabled(True)

    def show_code(self, code):
        self.code_label.setText(f'验证码: {code}')
        self.get_code_button.setEnabled(True)
        self.blacklist_button.setEnabled(False)

    def blacklist(self):
        blacklist_phone()
        self.phone_label.setText('手机号码: ')
        self.code_label.setText('验证码: ')
        self.copy_phone_button.setEnabled(False)
        self.get_code_button.setEnabled(False)
        self.blacklist_button.setEnabled(False)
        self.get_phone_button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())
    
