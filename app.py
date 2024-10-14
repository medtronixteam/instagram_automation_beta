import threading
import time
import requests
from flask import Flask, request, jsonify, make_response
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv
from functools import wraps
import os
import shutil
import pickle
import logging

load_dotenv("./.env")

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

file_handler = logging.FileHandler('logs.log', encoding='utf-8')
file_handler.setLevel(logging.ERROR)

formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S %p')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


app = Flask(__name__)

sessions_lock = threading.Lock()
sessions = []
stored_sessions = []


class InstagramAutomation:
    def __init__(self, **kwargs):
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36"

        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument('--headless')
        options.add_argument(f"user-agent={user_agent}")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-extensions")
        options.add_argument("--proxy-server='direct://'")
        options.add_argument("--proxy-bypass-list=*")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument('--disable-software-rasterizer')
        options.add_argument("--disable-dev-shm-usage")
        # options.binary_location = "./chrome-win64/chrome.exe"
        # service = Service(executable_path="./chromedriver/chromedriver.exe")
        options.binary_location = "/usr/local/bin/chrome-linux64/chrome"
        service = Service(executable_path="/usr/local/bin/chromedriver-linux64/chromedriver")

        self.driver = webdriver.Chrome(service=service, options=options)

        self.name = kwargs.get('name', None)
        self.email = kwargs.get('email', None)
        self.password = kwargs.get('password', None)
        self.asset_id = kwargs.get('asset_id', None)
        self.uid = kwargs.get('uid', None)
        self.cookies = kwargs.get('cookies', None)
        self.resume = kwargs.get('resume', False)
        self.stoped= False

        self.thread = threading.Thread(target=self.start_session)
        self.thread.daemon = True


    def start_session(self):
        try:
            if not self.resume:
                login_status = self.login()
                if login_status == 404:
                    self.stop()
                    return

                inbox_status = self.go_to_inbox()
                if inbox_status == 404:
                    self.stop()
                    return
                
                self.save_session()
            
            else:
                resume_status = self.resume_session()
                if resume_status == 404:
                    self.stop()
                    return
            
            self.start_automation()
        
        except Exception as e:
            session_ = get_current_session(self.name)
            with sessions_lock:
                session_["status"] = "ERROR_OCCURRED"
                session_["message"] = "Something went wrong while starting your session. Please try again."
            logger.error(f"Exception in start_session: {e}")
            self.stop()



    def save_session(self):
        session_path = f".sessions/{self.name}"
        data = {"uid": self.uid, "asset_id": self.asset_id}
        os.makedirs(session_path, exist_ok=True)
        with open(f"{session_path}/data.pkl", "wb") as data_file:
            pickle.dump(data, data_file)
        with open(f"{session_path}/cookies.pkl", "wb") as cookies_file:
            pickle.dump(self.driver.get_cookies(), cookies_file)


    def resume_session(self):
        self.driver.get("https://www.facebook.com/")

        for cookie in self.cookies:
            self.driver.add_cookie(cookie)
        self.driver.refresh()
        inbox_status = self.go_to_inbox()
        if inbox_status == 404:
            logout_session(self.name)
            return 404


    def login(self):
        try:
            self.driver.get("https://www.facebook.com/")

            email = try_and_wait(self.driver.find_element, [By.ID, "email"], 1, 30)
            email.send_keys(self.email)

            password = try_and_wait(self.driver.find_element, [By.ID, "pass"], 1, 30)
            password.send_keys(self.password)

            password.send_keys(Keys.RETURN)

            session_ = get_current_session(self.name)
            # with sessions_lock:
            if self.check_login_errors(session_):
                return 404
            if self.check_auth_required(session_):
                return 202

            if self.is_home(1, 5):
                session_ = get_current_session(self.name)
                with sessions_lock:
                    session_["status"] = "LOGIN_SUCCESS"
                    session_["message"] = "Successfully loged in."
                return 200
            session_ = get_current_session(self.name)
            with sessions_lock:
                session_["status"] = "ERROR_OCCURRED"
                session_["message"] = "Something went wrong! Please Check your email and password and try again."
            return 404
                
        except Exception as e:
            logger.error(f"Exception in login: {e}")
            return 404
        

    def check_login_errors(self, session_):
        try:
            self.driver.find_element(By.XPATH, "//div[@class='_9ay7']")
            with sessions_lock:
                session_["status"] = "ERROR_OCCURRED"
                session_["message"] = "Invalid username or password."
            return True
        except:
            pass
        try:
            self.driver.find_element(By.XPATH, "//span[@class='_akzt']")
            with sessions_lock:
                session_["status"] = "ERROR_OCCURRED"
                session_["message"] = "Invalid username or password."
            return True
        except:
            pass
        try:
            self.driver.find_element(By.XPATH, "//div[@class='fsl fwb fcb']")
            with sessions_lock:
                session_["status"] = "ERROR_OCCURRED"
                session_["message"] = "You've entered an old password."
            return True
        except:
            pass


    def check_auth_required(self, session_):
        try:
            self.driver.find_element(By.XPATH, "//div[@class='x16n37ib']")
            with sessions_lock:
                session_["status"] = "AUTH_REQUIRED"
                session_["message"] = "Go to your Facebook account on another device and open the notification that we sent to approve this login. Please approve this login under 5 minutes or your session will expire."
            return True
        except:
            pass
        try:
            self.driver.find_element(By.XPATH, "//input[@id='approvals_code']")
            message = self.driver.find_element(By.XPATH, "//div[@class='_2w-j _50f4']")
            with sessions_lock:
                session_["status"] = "2FA_REQUIRED"
                session_["message"] = f"{message.text} Or just check your notifications in another browser or phone where you've logged in, and approve this login under 5 minutes or your session will expire."
            return True
        except:
            pass
        return False
    

    def is_home(self, timeout, retries):
        home = try_and_wait(self.driver.find_element, [By.XPATH, "//a[@aria-label='Home']"], timeout, retries)
        if home:
            return True
        return False
    
    
    def is_inbox(self, timeout, retries):
        self.driver.get(f"https://business.facebook.com/latest/inbox/all?asset_id={self.asset_id}")
        inbox = try_and_wait(self.driver.find_element, [By.XPATH, "//div[@aria-level='1']"], timeout, retries)
        if inbox:
            return True
        return False
    
    
    def get_instagram(self, timeout, retries):
        instagram = try_and_wait(self.driver.find_element, [By.XPATH, "//a[contains(@aria-label, 'Instagram')]"], timeout, retries)
        if instagram:
            return instagram
        return False
    
    def trust_this_device(self, timeout, retries):
        trust_this_device = try_and_wait(self.driver.find_element, [By.XPATH, "//div[@class='xod5an3 xw7yly9']"], timeout, retries)
        print("Trust this device inside:", trust_this_device.text)
        if trust_this_device:
            return trust_this_device
        return False
    

    def go_to_inbox(self):
        session_ = get_current_session(self.name)
        if session_["status"] == "AUTH_REQUIRED" or session_["status"] == "2FA_REQUIRED":
            trust_this_device = self.trust_this_device(3, 100)
            if trust_this_device:
                trust_this_device.click()
                if self.is_home(2, 30):
                    if self.is_inbox(2, 30):
                        instagram = self.get_instagram(2, 5)
                        if instagram:
                            self.driver.execute_script("arguments[0].click();", instagram)
                            is_connected_instagram = try_and_wait(self.driver.find_element, [By.XPATH, "//div[@aria-level='3']"], 2, 4)
                            if is_connected_instagram and \
                            is_connected_instagram.text == "Connect to Instagram to get more features":
                                with sessions_lock:
                                    session_["status"] = "ERROR_OCCURRED"
                                    session_["message"] = "Please connect your Instagram account to the facebook page and try again."
                                    return 404
                            with sessions_lock:
                                session_["status"] = "INBOX_SUCCESS"
                                session_["message"] = "Session is in inbox."
                                return 200
                        
                        with sessions_lock:
                            session_["status"] = "ERROR_OCCURRED"
                            session_["message"] = "Something went wrong! Please try again."
                            return 404
                    
                    with sessions_lock:
                        session_["status"] = "ERROR_OCCURRED"
                        session_["message"] = "Invalid asset ID."
                        return 404
                    
                with sessions_lock:
                            session_["status"] = "ERROR_OCCURRED"
                            session_["message"] = "Something went wrong! Please try again."
                            return 404
                
            with sessions_lock:
                session_["status"] = "ERROR_OCCURRED"
                session_["message"] = "You've not Authorized your session within 5 minutes."
                return 404


        if self.is_home(3, 20):
            print("Running this in secode if.")
            if self.is_inbox(2, 30):
                instagram = self.get_instagram(2, 5)
                if instagram:
                    self.driver.execute_script("arguments[0].click();", instagram)
                    is_connected_instagram = try_and_wait(self.driver.find_element, [By.XPATH, "//div[@aria-level='3']"], 2, 4)
                    if is_connected_instagram and \
                        is_connected_instagram.text == "Connect to Instagram to get more features":
                        with sessions_lock:
                            session_["status"] = "ERROR_OCCURRED"
                            session_["message"] = "Please connect your Instagram account to the facebook page and try again."
                            return 404
                    with sessions_lock:
                        session_["status"] = "INBOX_SUCCESS"
                        session_["message"] = "Session is in inbox."
                        return 200
                
                with sessions_lock:
                    session_["status"] = "ERROR_OCCURRED"
                    session_["message"] = "Something went wrong! Please try again."
                    return 404
            
            with sessions_lock:
                session_["status"] = "ERROR_OCCURRED"
                session_["message"] = "Invalid asset ID."
                return 404
        
        with sessions_lock:
            session_["status"] = "ERROR_OCCURRED"
            session_["message"] = "Something went wrong, please try again."
            return 404
                

    def start_automation(self):
        session_ = get_current_session(self.name)
        with sessions_lock:
            session_["status"] = "WORKING"
            session_["message"] = "Your session is working."

        while True:
            if self.stoped:
                break
            inbox = self.driver.find_elements(By.XPATH, "//div[@data-pagelet='GenericBizInboxThreadListViewBody']//div[@role='presentation']")
            for message in inbox:
                try:
                    is_new_message = message.find_elements(By.XPATH, ".//div[contains(@class, 'x117nqv4')]")
                    if is_new_message:
                        data = message.text.splitlines()
                        self.track_message_recive(data[0], self.name, data[1])

                        response = self.ihsan_ai_bot(self.uid, data[1])
                        if response:
                            self.driver.execute_script("arguments[0].click();", message)
                            text_area = try_and_wait(self.driver.find_element, [By.XPATH, "//textarea[@placeholder='Reply on Instagram…']"], 1, 30)
                            text_area.send_keys(response["response"])
                            text_area.send_keys(Keys.ENTER)
                            self.track_message_sent(data[0], self.name, response["response"])
                        else:
                            self.driver.execute_script("arguments[0].click();", message)
                            text_area = try_and_wait(self.driver.find_element, [By.XPATH, "//textarea[@placeholder='Reply on Instagram…']"], 1, 30)
                            text_area.send_keys("We'll be back soon!")
                            text_area.send_keys(Keys.ENTER)
                            self.track_message_sent(data[0], self.name, "We'll be back soon!")
                except Exception as e:
                    logger.debug(f"Exception in start_automation: {e}")

            time.sleep(2)


    def submit_code(self, code):
        code_input = try_and_wait(self.driver.find_element, [By.XPATH, "//input[@id='approvals_code']"], 1, 30)
        if code_input:
            code_input.send_keys(code)
            code_input.send_keys(Keys.RETURN)

            code_error = self.driver.find_elements(By.XPATH, "//span[@class='_1tp7']")

            if code_error:
                return 401, "The login code you entered doesn't match the one sent to your phone, Pleae check the number and try again."

            while True:
                submit_button = try_and_wait(self.driver.find_element, [By.XPATH, "//button[@id='checkpointSubmitButton']"], 2, 3)
                if submit_button:
                    self.driver.execute_script("arguments[0].click();", submit_button)
                    continue
                return 200, "Code accepted."
        return 401, "Invalid request."
            

    def track_message_recive(self, recieve_from, session_name, message_text):
        payload = {'from': recieve_from,
                'session_id': session_name,
                'message': message_text}
        url = f"{os.environ.get('INSTAGRAM_AI_TRACKING_URL')}/receive"
        try:
            requests.request("POST", url, data=payload)

        except Exception as e:
            logger.error(f"Exception in track_message_recive: {e}")
            return

    
    def track_message_sent(self, sent_to, session_name, bot_response):
        payload = {'to': sent_to,
                'session_id': session_name,
                'message': bot_response}
        url = f"{os.environ.get('INSTAGRAM_AI_TRACKING_URL')}/sent"
        try:
            requests.request("POST", url, data=payload)

        except Exception as e:
            logger.error(f"Exception in track_message_sent: {e}")
            return


    def ihsan_ai_bot(self, uid, message_text):
        try:
            form_data = {'uid' : uid, 
                        'query' : message_text}
            headers = {
                        'Authorization': os.environ.get("IHSAN_BOT_KEY")
                        }
            response = requests.post(os.environ.get("IHSAN_BOT_URL"), data=form_data, headers=headers)
            return response.json()
        
        except Exception as e:
            logger.error(f"Exception in ihsan_ai_bot: {e}")
            return
        
    
    def stop(self):
        try:
            self.stoped = True
            self.driver.quit()

        except Exception as e:
            logger.error(f"Exception in stop: {e}")
            return


    def screenshot(self):
        try:
            return self.driver.get_screenshot_as_base64()
        
        except Exception as e:
            logger.error(f"Exception in screenshot: {e}")
            return ""


def try_and_wait(func, args, timeout, retries):
    while retries > 0:
        try:
            element = func(*args)
            return element
        except Exception:
            retries -= 1
            time.sleep(timeout)
    return None


def get_current_session(name):
    print("in get_current_session")
    # with sessions_lock:
    for session in sessions:
        if name in session:
            return session
    return None
    

def get_sessions():
        return [x for x in os.scandir(".sessions")]
    

def logout_session(session_name):
    try:
        shutil.rmtree(f".sessions/{session_name}")
        return True

    except OSError as e:
        logger.debug(f"Exception in delete_session: {e.filename} - {e.strerror}")
        return False


def auth_required(func):
    @wraps(func)
    def auth_wraper(*args, **kwargs):
        provided_key = request.headers.get('Authorization')
        if provided_key == os.environ.get("AUTH_KEY"):
            return func(*args, **kwargs)
        
        return jsonify({"message": "Unauthorized"}), 401
    
    return auth_wraper


def restore_saved_sessions():
    for stored_session in stored_sessions:
        stored_session_name = stored_session.name
        if stored_session_name != '.gitkeep':
            restore_a_session(stored_session_name)


def restore_a_session(stored_session_name):
    try:
        session_path = f".sessions/{stored_session_name}"
        data = pickle.load(open(f"{session_path}/data.pkl", "rb"))
        cookies = pickle.load(open(f"{session_path}/cookies.pkl", "rb"))
        uid = data['uid']
        asset_id = data['asset_id']

        session_data = {
            "name": stored_session_name,
            "asset_id": asset_id,
            "uid": uid,
            "resume": True,
            "cookies": cookies,
        }

        with sessions_lock:   
            for session_ in sessions:
                if stored_session_name in session_:
                    if session_["status"] != "ERROR_OCCURRED":
                        return True
                    
                    obj = InstagramAutomation(**session_data)
                    session_[stored_session_name] = obj
                    session_["status"] = "STARTING"
                    session_["message"] = "Starting your session please wait."
                    obj.thread.start()
                    return True
                
        obj = InstagramAutomation(**session_data)
        with sessions_lock:
            sessions.append({stored_session_name: obj,
                "status" : "STARTING",
                "message": "Starting your session please wait."})
        obj.thread.start()
        return True
    
    except Exception as e:
        logger.error(f"Exception in restore_a_session: {e}")
        return    


@app.route('/')
@auth_required
def home():
    return {"Message": "Instagram AI is ready to fly."}


@app.route("/api/insta/sessions/start", methods=["POST"])
@auth_required
def api_start_session():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    asset_id = request.form.get("asset_id")
    uid = request.form.get("uid")

    stored_sessions = get_sessions()
    if any(stored_session.name == name for stored_session in stored_sessions):
        with sessions_lock:
            for session_ in sessions:
                if name in session_:
                    if session_["status"] != "ERROR_OCCURRED":
                        return make_response({"message": f"Session '{name}' is already in starting or working state."}, 400)
        restore_a_session(name)
        return make_response({"name": name,
                "status": "STARTING",
                "message": "Starting your session please wait."}, 201)
    
    session_data = {
        "name": name,
        "email": email,
        "password": password,
        "asset_id": asset_id,
        "uid": uid
    }

    with sessions_lock:
        for session_ in sessions:
            if name in session_:
                if session_["status"] != "ERROR_OCCURRED":
                    return make_response({"message": f"Session '{name}' is already in starting or working state."}, 400)
                
                obj = InstagramAutomation(**session_data)
                session_[name] = obj
                session_["status"] = "STARTING"
                session_["message"] = "Starting your session please wait."
                obj.thread.start()
                return make_response({"name": name,
                    "status": "STARTING",
                    "message": "Starting your session please wait."}, 201)
        
    obj = InstagramAutomation(**session_data)
    with sessions_lock:
        sessions.append({name: obj,
            "status" : "STARTING",
            "message": "Starting your session please wait."})

    obj.thread.start()
    return make_response({"name": name,
        "status": "STARTING",
        "message": "Starting your session please wait."}, 201)


@app.route("/api/insta/sessions", methods=["GET"])
@auth_required
def return_sessions():
    try:
        sessions_data = []
        with sessions_lock:
            for session_ in sessions:
                sessions_data.append({"name": list(session_.keys())[0],
                                    "status": session_["status"],
                                    "message": session_["message"]})
        return sessions_data
    except Exception as e:
        logger.error(f"Exception in return_sessions: {e}")
        return []
    

@app.route("/api/insta/status/session", methods=["GET"])
@auth_required
def return_session_status():
    try:
        session = request.args.get('session')
        with sessions_lock:
            for session_ in sessions:
                if session in session_:
                    return {"name": list(session_.keys())[0],
                            "status": session_["status"],
                            "message": session_["message"]}
        return make_response({
                  "statusCode": 404,
                  "message": f"We didn't find a session with name '{session}'. Please start it first by using POST /sessions/start request",
                  "error": "Not Found"
                }, 404)
    
    except Exception as e:
        logger.error(f"Exception in return_session_status: {e}")
        return {}
    

@app.route("/api/insta/screenshot", methods=["GET"])
@auth_required
def api_get_screenshot():
    try:
        session = request.args.get('session')
        with sessions_lock:
            for session_ in sessions:
                if session in session_ and session_["status"] == "ERROR_OCCURRED":
                    return make_response({
                    "name": list(session_.keys())[0],
                    "status": session_["status"],
                    "message": session_["message"]
                    }, 404)
                return session_[session].screenshot()
            
        return make_response({
                  "statusCode": 404,
                  "message": f"We didn't find a session with name '{session}'. Please start it first by using POST /sessions/start request",
                  "error": "Not Found"
                }, 404)
    
    except Exception as e:
        logger.error(f"Exception in api_get_screenshot: {e}")
        return ""


@app.route("/api/insta/sessions/stop", methods=["POST"])
@auth_required
def api_stop_session():
    try:
        session = request.form.get("session")
        logout: bool = request.form.get("logout", False)

        with sessions_lock:
            for session_ in sessions:
                if session in session_:
                    if session_["status"] != "ERROR_OCCURRED":
                        session_[session].stop()
                    sessions.remove(session_)
                    if logout:
                        logout_session(session)
                    return {"name": session,
                            "status": "STOPED"}
        return make_response({
                    "statusCode": 404,
                    "message": f"We didn't find a session with name '{session}'. Please start it first by using POST /sessions/start request",
                    "error": "Not Found"
                    }, 404)
    
    except Exception as e:
        logger.error(f"Exception in api_stop_session: {e}")
        return ""
    

@app.route("/api/insta/sessions/logout", methods=["POST"])
@auth_required
def api_logout_session():
    try:
        session = request.form.get("session")

        with sessions_lock:
            for session_ in sessions:
                if session in session_:
                    if session_["status"] != "ERROR_OCCURRED":
                        session_[session].stop()
                    sessions.remove(session_)
        status = logout_session(session)
        if status:
            return make_response({"name": session,
                        "status": "LOGGEDOUT"}, 200)
        return make_response({
                    "statusCode": 404,
                    "message": f"Session not exists.",
                    "error": "Not Found"
                    }, 404)
    
    except Exception as e:
        logger.error(f"Exception in api_logout_session: {e}")
        return ""


@app.route("/api/insta/2fa/code", methods=["POST"])
@auth_required
def code_auth():
    try:
        session = request.form["session"]
        code = request.form["code"]
        with sessions_lock:
            for session_ in sessions:
                if session in session_:
                    if session_["status"] == "2FA_REQUIRED":
                        _, message = session_[session].submit_code(code)
                        if _ == 200:
                            return make_response({
                                "status": "SUCCESS",
                                "message": message
                                }, 200)
                        return make_response({
                                "status": "ERROR_OCCURRED",
                                "message": message
                                }, 401)

                    if session_["status"] == "ERROR_OCCURRED":
                        return make_response({
                        "name": list(session_.keys())[0],
                        "status": session_["status"],
                        "message": session_["message"]
                        }, 404)
            
        return make_response({
                  "statusCode": 404,
                  "message": f"We didn't find a session with name '{session}'. Please start it first by using POST /sessions/start request",
                  "error": "Not Found"
                }, 404)
    
    except Exception as e:
        logger.error(f"Exception in restore_a_session: {e}")
        return ""


@app.route("/api/insta/threads", methods=["GET"])
@auth_required
def return_threads():
    return [thread.name for thread in threading.enumerate()]


stored_sessions = get_sessions()
# print(stored_sessions)
if stored_sessions:
    restore_sessions_thread = threading.Thread(target=restore_saved_sessions)
    restore_sessions_thread.daemon = True
    restore_sessions_thread.start()


# if __name__ == '__main__':
#     app.run(host="0.0.0.0", port=6000)
