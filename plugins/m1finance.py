#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Extract transactions from M1 Finance.
"""

__version__ = '0.0.1'
required = ['selenium>=4.0.0', 'pyotp']

import pathlib
import meerschaum as mrsm
from meerschaum.utils.typing import Dict, Any, SuccessTuple
from meerschaum.config import get_plugin_config, write_plugin_config
from meerschaum.utils.prompt import prompt, get_password

from meerschaum.config._paths import PLUGINS_TEMP_RESOURCES_PATH
COOKIES_PATH: pathlib.Path = PLUGINS_TEMP_RESOURCES_PATH / 'm1_cookies.pkl'

def ask_for_credentials() -> Dict[str, str]:
    """
    Prompt the user for credentials.
    """
    username = prompt("M1 Finance username:")
    password = get_password(username)
    otp = prompt("16-digit 2FA secret:", is_password=True)
    return {
        'username': username,
        'password': password,
        'otp': otp,
    }

def register(pipe: mrsm.Pipe) -> Dict[str, Any]:
    """
    Prompt for credentials if necessary and return the pipe's parameters.
    """
    cf = get_plugin_config(warn=False) or ask_for_credentials()
    write_plugin_config(cf)
    parameters = pipe.parameters
    if parameters.get('columns', None):
        return parameters
    return {
        'columns': {
            'datetime': 'timestamp',
            'ticker': 'ticker',
        },
    }

_driver = None
def get_driver():
    """
    Return the headless Selenium Web Driver.
    """
    global _driver, _driver_location
    if _driver is not None:
        return _driver
    from selenium import webdriver
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options

    options = Options()
    #  options.add_argument('--headless')
    #  options.add_argument('--window-size=1920x1080')
    _driver = webdriver.Firefox(
        service = FirefoxService(),
        options = options,
    )
    return _driver

import atexit
def exit_handler():
    try:
        if _driver is not None:
            _driver.quit()
    except Exception as e:
        pass
atexit.register(exit_handler)

XPATHS: Dict[str, str] = {
    'username-input': "/html/body/div[2]/div/div/div[2]/div[2]/div[1]/div/form/div[2]/div/div[1]/div/input",
    'password-input': "/html/body/div[2]/div/div/div[2]/div[2]/div[1]/div/form/div[2]/div/div[2]/div/input",
    'login-button': "/html/body/div[2]/div/div/div[2]/div[2]/div[1]/div/form/div[4]/div/button",
    '2fa-input': "/html/body/div[2]/div/div/div[2]/div[2]/div/div/form/div/div/input",
    '2fa-button': "/html/body/div[2]/div/div/div[2]/div[2]/div/div/form/button",
    #  '2fa-button': "/html/body/div[2]/div/div/div[2]/div[2]/div/div/form/div",
}

def login_to_m1(driver):
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By
    from pyotp import TOTP
    wait = WebDriverWait(driver, 5)
    driver.implicitly_wait(0.5)

    cf = get_plugin_config(warn=False)
    if not cf:
        cf = ask_for_credentials()
        write_plugin_config(cf)
    username, password, otp = cf['username'], cf['password'], cf['otp']

    driver.get("https://dashboard.m1.com/login")
    wait.until(EC.visibility_of_element_located((By.XPATH, XPATHS['username-input'])))
    driver.find_element(By.XPATH, XPATHS['username-input']).send_keys(username)
    driver.find_element(By.XPATH, XPATHS['password-input']).send_keys(password)
    driver.find_element(By.XPATH, XPATHS['login-button']).click()

    totp = TOTP(otp)
    token = totp.now()

    import time
    wait.until(EC.visibility_of_element_located((By.XPATH, XPATHS['2fa-input'])))
    driver.find_element(By.XPATH, XPATHS['2fa-input']).send_keys(token)
    wait.until(EC.element_to_be_clickable((By.XPATH, XPATHS['2fa-button'])))
    time.sleep(1)
    driver.find_element(By.XPATH, XPATHS['2fa-button']).click()


def fetch(pipe: mrsm.Pipe, **kwargs):
    """
    Fetch the latest transactions from M1 Finance.
    """
