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

    if config.get("cache_hour_limit"):
        logging.info(
            f"Changing cache hour limit from {qq.cache_hour_limit} to {config.get('cache_hour_limit')}")
        qq.cache_hour_limit = config.get(
            'cache_hour_limit', qq.cache_hour_limit)

    # Select queryables to run
    cls = queryables_dict.get(cls and cls.value or "")
    cls_list = [cls] if cls else queryables_list

    if not cls_list:
        print("No queryables to run")
        return

    s = c.status("[status]Starting", spinner="bouncingBar")

    if not debug:
        s.start()
        print("\n" * 2)

    for cls in cls_list:
        try:
            run_queryable(cls, s, query=query, all_pages=show_everything)
        except (NotImplementedError, qq.MissingCookiesError,
                qq.ExpiredCookiesError) as e:
            if debug:
                logging.error(e)
            else:
                print(e, justify="center")
        except Exception as e:
            if debug:
                rich_log.exception(e)
            elif hasattr(cls, "NAME"):
                print(f"{cls.NAME()} - Error: {e}", justify="center")
            else:
                print(e, justify="center")
        if not debug:
            print("\n" * 2)
    s.stop()


def run_queryable(cls: Queryable, s: Status, **kwargs):

    if not cls or not issubclass(cls, Queryable):
        raise Exception(f"{cls} is not a valid Queryable.")

    s.update(f"[status]Requesting {cls.NAME()} data...")

    data = cls.make_request(**kwargs, **config.get(cls.__name__, {}))

    if not isinstance(data, dict):
        raise Exception("make_request() didn't return a data structure.")

    if not data:
        raise Exception("make_request() returned a empty data structure.")

    if not isinstance(data.get("entries"), list):
        raise Exception(
            "make_request() didn't return a valid list of entries.")

    cls.log(logging.debug,
            f"data['entries'] = {data.setdefault('entries', {})}")
    cls.log(logging.info, f"len(data['entries']) == {len(data['entries'])}")
    cls.log(
        logging.info,
        f"data = {(lambda d: (d.pop('entries') or True) and d)(data.copy())}")

    if not data.get("entries"):
        raise Exception("0 entries found.")

    s.update(f"[status]Parsing {cls.NAME()} data...")
    data = cls.parse_data(data)
    if not data["entries"]:
        raise Exception("every entry was removed during parsing of data.")

    cls.log(logging.debug, f"parsed data['entries'] = {data['entries']}")

    s.update(f"[status]Creating table for {cls.NAME()}...")
    table = cls.make_table(data)

    print(table, justify="center")


if __name__ == "__main__":
    logging.basicConfig(datefmt="[%X]",
                        handlers=[RichHandler(rich_tracebacks=True)])
    traceback.install()
    app()
