import logging
import requests
import re
from bs4 import BeautifulSoup, Tag
from rich.table import Table
from time import sleep
from functools import reduce
from math import ceil


def with_style(s, style): return f"[{style}]{s}[/]"


def get_tag(text, tag): return BeautifulSoup(text, 'html.parser').find(tag)
def get_attr(tag, attr): return str((tag and tag.get(attr)) or "").strip()
def get_href(tag): return get_attr(tag, "href")
def get_body(tag): return str((tag and tag.string) or "").strip()


def as_int(s): return int(re.sub(r"\D*", '', s) or 0)


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
    def log_response(cls, res: requests.Response, page: int, total: int, remaining: int) -> None:
        if res.status_code == 200:
            cls.log(
                logging.info, f"Requested page {page}: received {total} total entries with {remaining} remaining.")
        else:
            cls.log(logging.warning,
                    f"Request failed: {res.reason} ({res.status_code}).")

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