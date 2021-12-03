import logging
import re
import json
import datetime
from os.path import dirname, realpath
from bs4 import BeautifulSoup, Tag
from rich.table import Table
from rich.markup import escape
from time import sleep
from functools import reduce
from math import ceil
import asyncio
import aiohttp

CACHE_FILE = dirname(dirname(realpath(__file__))) + "/cache.json"
MAX_SYNC_REQUESTS = 5
MIN_TESTS = 2
RECURSIVE_DELAY = 0.5

cache_hour_limit = 6
strip_http = True

_cache = None


def with_style(s, style): return f'[{style}]{escape(s)}[/]'


def as_link(link, _strip_http: bool = None):
    if _strip_http is None:
        _strip_http = strip_http
    return '[link={}]{}[/link]'.format(link, escape(
        re.sub(r"^(https?://)?(www\.)?", '', link) if _strip_http else link))


def get_tag(text, tag): return BeautifulSoup(text, 'html.parser').find(tag)
def get_attr(tag, attr): return str((tag and tag.get(attr)) or "").strip()
def get_href(tag): return get_attr(tag, "href")
def get_body(tag): return str((tag and tag.string) or "").strip()


def as_int(s): return int(re.sub(r"\D*", '', s) or 0)


def ceildiv(a, b):
    return -(a // -b)


def save_cache():
    global _cache

    if _cache is None or not _cache:
        logging.info("Tried to save empty Cache")
        return

    try:
        with open(CACHE_FILE, "w", encoding='utf-8') as f:
            # logging.debug(f"Saving cache: {_cache}") # Too much info
            # Dumping directly into file can break a valid cache file
            string = json.dumps(_cache, ensure_ascii=False, indent=2)
            f.write(string)
            logging.info(f"Saved cache")
    except Exception as e:
        logging.error(f"Exception ocurred while writing cache file: {e}")


def open_cache(force: bool = False):
    global _cache

    if not force and _cache is not None:
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
                _cache = data
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

    if _cache is None:
        logging.info("Creating empty Cache")
        _cache = {}


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
    def log_response(cls, res: aiohttp.ClientResponse) -> None:
        if not res:
            cls.log(logging.warn, f"Request Failed: Response object is {res}")
        else:
            cls.log(logging.info if res.ok else logging.warn,
                    f"Requested URL with response: {res.reason} ({res.status})" +
                    f"\n{res.url}")

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
        global _cache
        open_cache()

        logging.info(f"Writing cache['{cls.__name__}']['{key}']")
        time = datetime.datetime.today()
        _cache.setdefault(cls.__name__, {})[key] = (time.isoformat(), value)

        save_cache()

    @classmethod
    def read_cache(cls, key):
        global _cache
        open_cache()

        if not _cache:
            logging.info("Cache is empty")
            return

        if _cache and cls.__name__ in _cache:
            logging.info(f"Getting cache['{cls.__name__}']['{key}']")

            time_s, value = _cache.get(
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
    async def make_request(cls, query: str, session: aiohttp.ClientSession, all_pages=False, page=0, length=30, **kwargs) -> dict:
        """ query is assumed to be lowercase and stripped """
        raise NotImplementedError(
            f"{cls.NAME()} - Internet Request has not yet been implemented.")

        start = page * length

        url = cls.END_POINT
        params = {**kwargs.get("params", {})}

        async with session.get(url=url, params=params) as res:
            cls.log_response(res)
            # j = (res.ok and await res.json(content_type=None)) or {}
            content = (res.ok and await res.text()) or ""
            soup = BeautifulSoup(content, 'html.parser')

        trs = soup.find_all("tr", class_=re.compile(r"^CLASS$"))
        # assuming trs is already filtered by query

        entries = kwargs.get("entries", [])
        entries.extend(trs[start:])

        if not all_pages:
            del entries[length:]

        total = len(trs)
        showing = len(entries)
        remaining = max(0, total - (start + showing))

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
                as_link(cell['page']),
                style=style
            )

        return t


async def _make_php_request(
        cls,
        query: str,
        session: aiohttp.ClientSession,
        SITE_PAGE_LENGTH: int,

        url: str = None,
        params: dict = None,
        search_total=None,
        get_trs=None,

        all_pages: bool = False,
        page: int = 0,
        length: int = 30,
        **kwargs
) -> dict:

    data = {
        "entries": [],
        "start": page * length,
        "showing": 0,
        "remaining": 0,
        "total": 0,
        **kwargs.get("data", {})
    }

    if url is None:
        url = cls.END_POINT + "browse.php"
    if params is None:
        params = {"page": 0, "search": query}
    if not get_trs:
        def get_trs(soup): return soup.find_all("tr")

    cookies = kwargs.get("cookies", {})
    needed_cookies = kwargs.get("needed_cookies", set())

    cls.raise_if_missing_cookies(cookies, needed_cookies)

    fails = 0

    site_page_start = (data['start'] + data['showing']) // SITE_PAGE_LENGTH

    async def get_page_trs(i: int):
        nonlocal fails
        params['page'] = site_page_start + i

        async with session.get(url=url, params=params, cookies=cookies) as res:
            cls.log_response(res)
            content = (res.ok and await res.read()) or ""
            soup = BeautifulSoup(content, 'html.parser')

            cls.raise_if_expired_cookies(
                soup.find("form", action="takelogin.php", method="post"))

            # logging.debug(soup.prettify())
            fails += not res.ok

            trs = get_trs(soup=soup)

            if search_total:
                # Since a request can fail, get maximum value for all
                data['total'] = max(
                    data['total'], search_total(soup=soup, trs=trs))

            return trs

    if all_pages:
        needed = ceildiv(data['remaining'], SITE_PAGE_LENGTH) or MIN_TESTS
    else:
        needed = ceildiv(length - data['showing'], SITE_PAGE_LENGTH)

    needed = min(needed, MAX_SYNC_REQUESTS)

    for trs in await asyncio.gather(*[get_page_trs(i) for i in range(needed)]):
        data['entries'].extend(trs)

    # If is the first recursive iteration - remove what is before start
    if not 'data' in kwargs:
        del data['entries'][:data['start'] % SITE_PAGE_LENGTH]

    # Limit entries to length
    if not all_pages:
        del data['entries'][length:]

    data['showing'] = len(data['entries'])
    data['total'] = max(data['total'], data['showing'])
    data['remaining'] = max(
        0, data['total'] - (data['start'] + data['showing']))

    if not fails and data['remaining'] and (all_pages or data['showing'] < length):
        sleep(RECURSIVE_DELAY)
        return await _make_php_request(
            cls=cls,

            query=query,
            session=session,
            SITE_PAGE_LENGTH=SITE_PAGE_LENGTH,

            url=url,
            params=params,
            search_total=search_total,
            process_trs=process_trs,


            all_pages=all_pages,
            page=page,
            length=length,

            **{**kwargs, 'data': data}
        )

    return data
