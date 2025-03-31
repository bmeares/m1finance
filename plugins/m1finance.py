#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Extract transactions from M1 Finance.
"""

__version__ = '0.0.2'
required = ['selenium>=4.0.0', 'pyotp', 'requestium', 'selenium-wire', 'selenium-stealth', 'blinker==1.7.0']

import pathlib
import pickle
import time
import json
import copy
from datetime import datetime, timedelta
import meerschaum as mrsm
from meerschaum.utils.typing import Dict, Any, SuccessTuple, Tuple, Optional, List
from meerschaum.config import get_plugin_config, write_plugin_config
from meerschaum.utils.prompt import prompt, get_password
from meerschaum.utils.warnings import warn
from meerschaum.utils.debug import dprint

def ask_for_credentials() -> Dict[str, str]:
    """
    Prompt the user for credentials.
    """
    username = prompt("M1 Finance username (email):")
    password = get_password(username)
    otp = prompt("16-digit 2FA secret:", is_password=True)
    return {
        'username': username,
        'password': password,
        'otp': otp,
    }

def setup() -> SuccessTuple:
    """
    Save credentials on plugin setup.
    """
    cf = get_plugin_config(warn=False) or ask_for_credentials()
    write_plugin_config(cf)
    return True, "Success"

def register(pipe: mrsm.Pipe) -> Dict[str, Any]:
    """
    Prompt for credentials if necessary and return the pipe's parameters.
    """
    _ = setup()
    parameters = pipe.parameters
    if parameters.get('columns', None):
        return parameters
    return {
        'columns': {
            'datetime': 'date',
            'id': 'id',
        },
    }

_driver = None
def get_session():
    """
    Return the headless Selenium Web Driver.
    """
    global _driver, _driver_location
    if _driver is not None:
        return _driver

    with mrsm.Venv('m1finance'):
        import blinker
        from seleniumwire.webdriver import Chrome
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.options import Options
        from requestium import Session
        from selenium_stealth import stealth


    options = Options()
    #  options.add_argument('--headless')
    options.add_argument('--lang=en_US')
    #  options.add_argument('--window-size=1920,1080')
    #  options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    #  options.add_argument('--no-sandbox')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36")
    _driver = Chrome(
        service = ChromeService(),
        options = options,
    )
    _driver.implicitly_wait(15)
    stealth(
        _driver,
        languages = ["en-US", "en"],
        vendor = "Google Inc.",
        platform = "Win32",
        webgl_vendor = "Intel Inc.",
        renderer = "Intel Iris OpenGL Engine",
        fix_hairline = True,
    )
    return Session(driver=_driver)

import atexit
def exit_handler():
    try:
        if _driver is not None:
            _driver.quit()
    except Exception as e:
        pass
atexit.register(exit_handler)

XPATHS: Dict[str, str] = {
    #  'username-input': '//*[@id="root"]/div/div/div[2]/div[2]/div[1]/div/form/div[2]/div/div[1]/div/input',
    'username-input': '//input[@name="username"]',
    #  'username-input': "/html/body/div[2]/div/div/div[2]/div[2]/div[1]/div/form/div[2]/div/div[1]/div/input",
    'password-input': '//input[@name="password"]',
    #  'password-input': '//*[@id="root"]/div/div/div[2]/div[2]/div[1]/div/form/div[2]/div/div[2]/div/input',
    #  'password-input': "/html/body/div[2]/div/div/div[2]/div[2]/div[1]/div/form/div[2]/div/div[2]/div/input",
    'login-button': '//*[@id="root"]/div/div/div[2]/div[2]/div[1]/div/form/div[4]/div/button',
    #  'login-button': "/html/body/div[2]/div/div/div[2]/div[2]/div[1]/div/form/div[4]/div/button",
    #  '2fa-input': "/html/body/div[2]/div/div/div[2]/div[2]/div/div/form/div/div/input",
    '2fa-input': '//input[@name="code"]',
    #  '2fa-button': "/html/body/div[2]/div/div/div[2]/div[2]/div/div/form/button",
    '2fa-button': '//button[@type="submit"]',
    'invest': '/html/body/div[2]/div/div/div/div[2]/div/div/nav/div[2]/div[3]/div/div',
    'first-account': '/html/body/div[2]/div/div/div/div[2]/div/div/nav/div[2]/div[5]/div/div/div/p',
    'activity': '/html/body/div[2]/div/div/div/div[2]/div/div/div/nav/div/div[1]/a[2]/div/p',
    #  'activity-table': '/html/body/div[2]/div/div/div/div[2]/div/div/div/div[2]/div/div/div/div[2]/div/div',
    'activity-table': '//div[@data-testid="table-grid-cell"]',
}

URLS: Dict[str, str] = {
    'dash': "https://dashboard.m1.com/",
    'login': "https://dashboard.m1.com/login",
    'graphql': 'https://lens.m1.com/graphql',
    'home': 'https://dashboard.m1.com/d/home',
}

def login_to_m1(session):
    """
    Sign into the M1 login page and return the request credentials.
    """
    if _account_id is not None:
        return _account_id, _auth

    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By
    from pyotp import TOTP
    
    wait = WebDriverWait(session.driver, 10)

    cf = get_plugin_config(warn=False)
    if not cf:
        cf = ask_for_credentials()
        write_plugin_config(cf)
    username, password, otp = cf['username'], cf['password'], cf['otp']

    session.driver.get(URLS['login'])
    wait.until(EC.visibility_of_element_located((By.XPATH, XPATHS['username-input'])))
    session.driver.find_element(By.XPATH, XPATHS['username-input']).send_keys(username)
    session.driver.find_element(By.XPATH, XPATHS['password-input']).send_keys(password)
    session.driver.ensure_element("xpath", XPATHS['login-button'], state='clickable').ensure_click()

    totp = TOTP(otp)
    token = totp.now()

    time.sleep(1)
    session.driver.ensure_element("xpath", XPATHS['2fa-input']).send_keys(token)
    button = session.driver.ensure_element("xpath", XPATHS['2fa-button'], state='clickable')
    time.sleep(1)
    button.ensure_click()
    wait.until(EC.url_to_be(URLS['home']))
    return get_auth_creds(session)


_account_id, _auth = None, None
def get_auth_creds(session) -> Tuple[str, str]:
    """
    Return a tuple of the account ID and authorization token.
    """
    global _account_id, _auth
    if _account_id is not None:
        return _account_id, _auth

    session.driver.get(URLS['home'])
    session.driver.ensure_element("xpath", XPATHS['invest'], state='clickable').ensure_click()
    session.driver.ensure_element("xpath", XPATHS['first-account'], state='clickable').ensure_click()
    session.driver.ensure_element("xpath", XPATHS['activity'], state='clickable').ensure_click()
    session.driver.ensure_element("xpath", XPATHS['activity-table'])

    auth, account_id = None, None
    for request in session.driver.requests:
        if 'authorization' not in request.headers:
            continue
        auth = request.headers['authorization']
        payload = json.loads(request.body)
        account_id = payload.get('variables', {}).get('id', None)
        if not account_id:
            continue
        break

    if not auth or not account_id:
        raise Exception("No auth token or account ID detected.")
    _account_id, _auth = account_id, auth
    return account_id, auth


def get_activities(
        session,
        begin: Optional[datetime] = None,
        end: Optional[datetime] = None,
        chunksize: Optional[int] = None,
        fetch_dividends: bool = True,
        fetch_trades: bool = True,
        fetch_transfers: bool = True,
        fetch_cash: bool = True,
        fetch_positions: bool = True,
        symbols_to_fetch: Optional[List[str]] = None,
        debug: bool = False,
    ):
    """
    Query the activities endpoint for dividends.
    """
    begin_str = begin.date().isoformat() if begin else None
    end_str = (end.date() + timedelta(days=1)).isoformat() if end else None
    if chunksize is not None or chunksize <= 0:
        chunksize = 100

    account_id, auth = get_auth_creds(session)
    session.transfer_driver_cookies_to_session()

    query = """query GetInvestActivity($id: ID!, $first: Int, $after: String, $filter: InvestActivityEntryFilterInput, $sort: [InvestActivityEntrySortInput!]) {
  node(id: $id) {
    ...InvestActivity
    __typename
  }
}

fragment InvestActivity on Account {
  investActivity {
    activity(first: $first, after: $after, filter: $filter, sort: $sort) {
      pageInfo {
        ...PageInfo
        __typename
      }
      edges {
        node {
          ...InvestActivityNode
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
  __typename
}

fragment PageInfo on PageInfo {
  hasNextPage
  hasPreviousPage
  startCursor
  endCursor
  __typename
}

fragment InvestActivityNode on InvestActivityEntry {
  __typename
  id
  title
  date(local: true)
  description
  ... on InvestActivityTradeSummaryEntry {
    countOfBuys
    countOfSells
    amountOfBuys
    amountOfSells
    __typename
  }
  ... on InvestActivityTradeEntry {
    amount
    tradeSecurity {
      descriptor
      security {
        symbol
        name
        __typename
      }
      __typename
    }
    __typename
  }
  ... on InvestActivityCashEntry {
    amount
    isRelatedToSecurity
    cashSecurity {
      descriptor
      security {
        symbol
        name
        __typename
      }
      __typename
    }
    transferDetails {
      transferSummary
      transferId
      totalAmount
      __typename
    }
    __typename
  }
  ... on InvestActivityPositionEntry {
    quantity
    positionSecurity {
      descriptor
      security {
        symbol
        name
        __typename
      }
      __typename
    }
    __typename
  }
}"""
    request_payload: Dict[str, Any] = {
        'operationName': 'GetInvestActivity',
        'query': query,
        'variables': {
            'after': None,
            'filter': {
                'fromDate': begin_str,
                'includeCategoryCash': fetch_cash,
                'includeCategoryDividend': fetch_dividends,
                'includeCategoryPosition': fetch_positions,
                'includeCategoryTrading': fetch_trades,
                'includeCategoryTransfer': fetch_transfers,
                'symbols': symbols_to_fetch or [],
                'toDate': end_str,
            },
            'first': chunksize,
            'id': account_id,
            'sort': {
                'direction': 'DESC',
                'type': 'DATE',
            },
        },
    }

    headers = {
        'content-type': 'application/json',
        'authorization': auth,
    }

    all_rows = []
    has_next_page = True
    while has_next_page:
        response = session.post(URLS['graphql'], data=json.dumps(request_payload), headers=headers)
        if not response:
            warn("Failed to fetch page!")
            continue
        page_data = response.json()['data']
        if debug:
            dprint("Payload:")
            mrsm.pprint(request_payload)
            dprint("Page data:")
            mrsm.pprint(page_data)
        activity = page_data['node']['investActivity']['activity']
        if activity is None:
            break
        page_info = activity['pageInfo']
        end_cursor = page_info.get('endCursor')
        has_next_page = page_info['hasNextPage']
        request_payload['variables'].update({'after': end_cursor})
        all_rows.extend([row['node'] for row in activity['edges']])
    return all_rows


def fetch(
        pipe: mrsm.Pipe,
        begin: Optional[datetime] = None,
        end: Optional[datetime] = None,
        chunksize: Optional[int] = None,
        debug: bool = False,
        **kwargs
    ):
    """
    Fetch the latest transactions from M1 Finance.
    """
    session = get_session()
    account_id, auth_token = login_to_m1(session)
    if debug:
        dprint("Successfully logged into M1!")
    m1_params = pipe.parameters.get('m1finance', {})
    return get_activities(
        session,
        begin = begin,
        end = end,
        chunksize = chunksize,
        fetch_dividends = m1_params.get('dividends', True),
        fetch_trades = m1_params.get('trades', True),
        fetch_cash = m1_params.get('cash', True),
        fetch_positions = m1_params.get('positions', True),
        fetch_transfers = m1_params.get('transfers', True),
        symbols_to_fetch = m1_params.get('symbols', None),
        debug = debug,
    )
