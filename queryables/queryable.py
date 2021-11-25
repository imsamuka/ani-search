import logging
import requests
import re
import json
import datetime
from os.path import dirname, realpath
from bs4 import BeautifulSoup, Tag
from rich.table import Table
from time import sleep
from functools import reduce
from math import ceil

CACHE_FILE = dirname(dirname(realpath(__file__))) + "/cache.json"
cache_hour_limit = 6
cache = None


def with_style(s, style): return f"[{style}]{s}[/]"


def get_res_json(res: requests.Response) -> dict:
    return (res and (res.status_code == 200) and res.json()) or {}


def get_res_soup(res: requests.Response) -> BeautifulSoup:
    content = (res and (res.status_code == 200)
               and res.content) or "<html></html>"
    return BeautifulSoup(content, 'html.parser')


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
        if not isinstance(needed_cookies, set):
            logging.info(
                f"needed_cookies is {type(needed_cookies)} instead of set")
            return
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
        time = datetime.datetime.today()
        cache.setdefault(cls.__name__, {})[key] = (time.isoformat(), value)

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

            time_s, value = cache.get(
                cls.__name__, {}).get(key) or (None, None)

            if time_s is None or value is None:
                logging.info(f"cache doesn't exist or is invalid")
                return

            time = datetime.datetime.fromisoformat(time_s)
            dt = datetime.datetime.today() - time

            passed_hours = dt.seconds / 60 / 60
            cache_seconds = cache_hour_limit * 60 * 60

            logging.info(
                f"passed {dt.seconds} seconds since cached ({passed_hours:.4f} hours)")

            if dt.seconds < cache_seconds:
                logging.info(
                    f"cache still valid ({dt.seconds} < {cache_seconds}) seconds")
                return value

            logging.info(
                f"cache no longer valid ({dt.seconds} > {cache_seconds}) seconds")
            return

        logging.info(f"cache['{cls.__name__}'] doesn't exist")

    @classmethod
    def parse_data(cls, data: dict) -> dict:
        if data.get("parsed"):
            logging.info("Data already parsed")
            return data
        data["entries"] = cls.parse_entries(data.get("entries", []))
        data["parsed"] = True
        return data

    @classmethod
    def _Table(cls, data: dict) -> Table:
        t = Table(title_style="title_style", header_style="header_style")
        t.title = f"{cls.NAME()} - {data['total']} entries"
        if data['showing'] < data['total']:
            t.title += f" [dim white](Showing {data['showing']})[/]"
        return t

    @classmethod
    def make_request(cls, query: str, all_pages=False, page=0, length=30, **kwargs) -> dict:
        """ query is assumed to be lowercase and stripped """
        raise NotImplementedError(
            f"{cls.NAME()} - Internet Request has not yet been implemented.")

        start = page * length

        url = cls.END_POINT
        params = {}
        res = requests.get(url, {**params, **kwargs.get("params", {})})
        cls.log_response(res, page)

        # j = get_res_json(res)
        soup = get_res_soup(res)
        trs = soup.find_all("tr", class_=re.compile(r"^CLASS$"))
        # assiming trs is already filtered by query

        entries = kwargs.get("entries", [])
        entries.extend(trs[start:] if all_pages else trs[start:start+length])

        total = len(trs)
        showing = len(entries)
        remaining = total - (start + showing)
        if remaining < 0:
            remaining = 0

        return {
            "entries": entries,
            "start": kwargs.get("rec_start", start),
            "showing": showing,
            "remaining": remaining,
            "total": total,
        }

    @classmethod
    def parse_entries(cls, entries: list) -> list[dict]:
        new_entries = []

        for entry in entries:

            raise NotImplementedError(
                f"{cls.NAME()} - Data parsing has not yet been implemented.")

            new_entries.append({
                "title": "",
                "type": "",
                "page": "",
                "command": "",

                "size": "",
                "seeds": 0,
                "leechers": 0,
                "completions": 0,
            })

        return new_entries

    @classmethod
    def make_table(cls, data: dict) -> Table:
        t = cls._Table(data)

        raise NotImplementedError(
            f"{cls.NAME()} - Table construction has not yet been implemented.")

        t.add_column("Title")
        t.add_column("Type", justify="center")
        t.add_column("Size", justify="right", style="white")
        t.add_column("Page Link", style="dim")

        for entry in data['entries']:

            style = ""
            if cell['seeds'] == 0:
                style += " dim"

            type_style = {
                "Episodes": "episodes",
                "Complete": "complete",
                "OVA": "special",
                "Movie": "movie",
            }.get(cell['type'], "white")

            t.add_row(
                cell['title'],
                with_style(cell['type'], type_style),
                cell['size'],
                cell['page'],
                style=style
            )

        return t
