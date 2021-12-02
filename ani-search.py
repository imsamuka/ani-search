#!/usr/bin/env python

import logging
from typer import Typer
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
from rich.status import Status
from rich import traceback

from os.path import dirname, realpath
import json
import asyncio
from aiohttp import ClientSession

import queryables.queryable as qq
from queryables.queryable import Queryable
from queryables import queryables_list, queryables_enum, queryables_dict

CONFIG_FILE = dirname(realpath(__file__)) + "/config.json"

config = {}
rich_log = logging.getLogger("rich")
app = Typer()

c = Console(theme=Theme({
    "irc": "underline",
    "movie": "bright_red bold",
    "special": "gold1",
    "nsfw": "deep_pink2 italic",
    "episodes": "green_yellow",
    "complete": "green3 bold",
    "title_style": "bold green",
    "header_style": "bold green",
    "status": "bold green"
}))

print = c.print


@app.command()
def search(
    query: str,
    show_everything: bool = False,
    debug: bool = False,
    cls: queryables_enum = None,
    strip_http: bool = None
):
    query = query.strip().lower()
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Read config file
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise Exception(
                    f"Config file should always be a {dict}, not a {type(data)}"
                )

            global config
            config = data
    except FileNotFoundError as e:
        if debug:
            rich_log.exception(e)
    except json.JSONDecodeError as e:
        if debug:
            rich_log.exception(e)
        else:
            print(f"\nCouldn't decode config file:\n{e}\n", justify="center")
    except Exception as e:
        if debug:
            rich_log.exception(e)
        else:
            print('\n', e, '\n', justify="center")

    if config.get('cache_hour_limit'):
        logging.info(
            f"Changing cache hour limit from {qq.cache_hour_limit} to {config.get('cache_hour_limit')}")
        qq.cache_hour_limit = config.get(
            'cache_hour_limit', qq.cache_hour_limit)

    if strip_http is not None:
        logging.info(
            f"Changing strip_http from {qq.strip_http} to {strip_http}")
        qq.strip_http = strip_http
    elif config.get('strip_http') is not None:
        logging.info(
            f"Changing strip_http from {qq.strip_http} to {config.get('strip_http')}")
        qq.strip_http = config.get('strip_http')

    # Select queryables to run
    cls = queryables_dict.get(cls and cls.value or "")
    cls_list = [cls] if cls else queryables_list

    if not cls_list:
        print("No queryables to run")
        return

    status = c.status("[status]Starting", spinner="bouncingBar")

    if not debug:
        status.start()
        print("\n" * 2)

    asyncio.run(
        tryq_wrapper(cls_list, debug=debug, status=status,
                     query=query, all_pages=show_everything))

    status.stop()


async def tryq_wrapper(cls_list, **kwargs):
    async with ClientSession() as session:
        await asyncio.gather(*[
            try_queryable(cls=cls, session=session, **kwargs)
            for cls in cls_list])


async def try_queryable(cls: Queryable, debug: bool, status: Status, **kwargs):
    if not (isinstance(cls, type) and issubclass(cls, Queryable)):
        print(f"{cls} is not a valid Queryable.", justify="center")

    try:
        status.update(f"Starting {cls.NAME()}")
        await run_queryable(cls=cls, status=status, **kwargs)
    except (NotImplementedError, qq.MissingCookiesError, qq.ExpiredCookiesError) as e:
        if debug:
            logging.error(e)
        else:
            print(e, justify="center")
    except Exception as e:
        if debug:
            rich_log.exception(e)
        else:
            print(f"{cls.NAME()} - Error: {e}", justify="center")

    if not debug:
        print("\n" * 2)


async def run_queryable(cls: Queryable, status: Status, **kwargs):

    status.update(f"[status]Requesting {cls.NAME()} data...")
    data = await cls.make_request(**{**kwargs, **config.get(cls.__name__, {})})

    assert isinstance(data, dict), "make_request() didn't return data dict."

    assert data, "make_request() returned empty a data dict."

    assert isinstance(data.get("entries"), list), (
        "make_request() didn't return a valid list of entries.")

    cls.log(logging.debug, f"{data['entries'] = }")
    cls.log(logging.info, f"{len(data['entries']) = }")
    cls.log(logging.info,
            f"data = {(lambda d: (d.pop('entries') or True) and d)(data.copy())}")

    assert data["entries"], "0 entries found."

    status.update(f"[status]Parsing {cls.NAME()} data...")
    data = cls.parse_data(data)

    assert data["entries"], "every entry was removed during parsing of data."

    cls.log(logging.debug, f"parsed {data['entries'] = }")

    status.update(f"[status]Creating table for {cls.NAME()}...")
    table = cls.make_table(data)

    assert table.row_count, "constructed table with no rows"

    print(table, justify="center")


if __name__ == "__main__":
    logging.basicConfig(datefmt="[%X]",
                        handlers=[RichHandler(rich_tracebacks=True)])
    traceback.install()
    app()
