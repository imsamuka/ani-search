import logging
import requests
import re
import json
from os.path import dirname, realpath
from bs4 import BeautifulSoup, Tag
from rich.table import Table
from time import sleep
from functools import reduce
from math import ceil

CACHE_FILE = dirname(dirname(realpath(__file__))) + "/cache.json"
cache = None


def with_style(s, style): return f"[{style}]{s}[/]"


def get_tag(text, tag): return BeautifulSoup(text, 'html.parser').find(tag)
def get_attr(tag, attr): return str((tag and tag.get(attr)) or "").strip()
def get_href(tag): return get_attr(tag, "href")
def get_body(tag): return str((tag and tag.string) or "").strip()


def as_int(s): return int(re.sub(r"\D*", '', s) or 0)


def save_cache():
    global cache

    if cache is None or not cache:
        logging.info("Tried to save empty Cache")
        return

    try:
        with open(CACHE_FILE, "w", encoding='utf-8') as f:
            logging.debug(f"Saving cache: {cache}")
            # Dumping directly into file can break a valid cache file
            string = json.dumps(cache, ensure_ascii=False, indent=2)
            f.write(string)
            logging.info(f"Saved cache")
    except Exception as e:
        logging.error(f"Exception ocurred while writing cache file: {e}")


def open_cache(force: bool = False):
    global cache

    if not force and cache is not None:
        logging.info("Cache was opened already")
        return

    try:
        with open(CACHE_FILE, "r", encoding='utf-8') as f:
            if not f.read().strip():
                logging.info("Cache file is empty")
                raise FileNotFoundError

            f.seek(0)
            data = json.load(f)

            if isinstance(data, dict):
                cache = data
                logging.info("Opened Cache")
            else:
                logging.warning(
                    f"Cache file is {type(data)} instead of {dict}. Ignoring it")
    except FileNotFoundError as e:
        pass
    except json.JSONDecodeError as e:
        logging.error(f"Couldn't decode cache file: {e}")
    except Exception as e:
        logging.error(f"Exception ocurred while reading cache file: {e}")

    if cache is None:
        logging.info("Creating empty Cache")
        cache = {}


class MissingCookiesError(Exception):
    pass


class ExpiredCookiesError(Exception):
    pass


class Queryable:

    END_POINT = ""

    @classmethod
    def NAME(cls):
        return cls.__name__.replace("_", " ")

    def __repr__(self):
        return f'Queryable<"{self.NAME()}", {self.END_POINT}>'

    @classmethod
    def log(cls, func, msg: str):
        msg = f"{cls.NAME()} - {msg}"
        if func:
            func(msg)
        return msg

    @classmethod
    def log_response(cls, res: requests.Response, page: int) -> None:
        if not res:
            cls.log(
                logging.info, f"Requested (page {page}) Failed: Response object is {res}")
        elif res.status_code == 200:
            cls.log(logging.info, f"Requested (page {page}) Succeed.")
        else:
            cls.log(
                logging.warning, f"Request (page {page}) Failed: {res.reason} ({res.status_code}).")

    @classmethod
    def raise_if_missing_cookies(cls, cookies, needed_cookies):
        if not needed_cookies.issubset(cookies.keys()):
            _error = f"{cls.NAME()} - Unable to request: Missing cookies { needed_cookies.difference(cookies.keys()) }."
            raise MissingCookiesError(_error)

    @classmethod
    def raise_if_expired_cookies(cls, expired):
        if expired:
            _error = f"{cls.NAME()} - Cookies expired or invalid: page is requiring login.\nLogin again at {cls.END_POINT}"
            raise ExpiredCookiesError(_error)

    @classmethod
    def write_cache(cls, key, value):
        global cache
        open_cache()

        logging.info(f"Writing cache['{cls.__name__}']['{key}']")
        cache.setdefault(cls.__name__, {})[key] = value

        save_cache()

    @classmethod
    def read_cache(cls, key):
        global cache
        open_cache()

        if not cache:
            logging.info("Cache is empty")
            return

        if cache and cls.__name__ in cache:
            logging.info(f"Getting cache['{cls.__name__}']['{key}']")
            return cache.get(cls.__name__, {}).get(key)

        logging.info(f"cache['{cls.__name__}'] doesn't exist")

    @classmethod
    def _Table(cls, data: dict) -> Table:
        t = Table(title_style="title_style", header_style="header_style")
        t.title = f"{cls.NAME()} - {data['total']} entries"
        if data['showing'] < data['total']:
            t.title += f" [dim white](Showing {data['showing']})[/]"
        return t

    @classmethod
    def make_request(cls, query: str, all_pages=False, page=0, length=25, **kwargs) -> dict:
        """ query is assumed to be lowercase and stripped """
        raise NotImplementedError(
            f"{cls.NAME()} - Internet Request has not yet been implemented.")

    @classmethod
    def parse_entries(cls, entries: list) -> list[dict]:
        raise NotImplementedError(
            f"{cls.NAME()} - Data parsing has not yet been implemented.")

    @classmethod
    def make_table(cls, data: dict) -> Table:
        t = cls._Table(data)
        raise NotImplementedError(
            f"{cls.NAME()} - Table construction has not yet been implemented.")
        return t
