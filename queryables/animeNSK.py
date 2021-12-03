from queryables.queryable import *
from queryables.queryable import _make_php_request


class AnimeNSK_Packs(Queryable):

    END_POINT = "https://packs.ansktracker.net/"

    @classmethod
    async def make_request(cls, query: str, session: aiohttp.ClientSession, all_pages=False, page=0, length=30, **kwargs) -> dict:
        entries = cls.read_cache("entries") or []
        start = page * length

        if not entries:
            url = cls.END_POINT + "index.php"
            params = {"Modo": "Packs", "bot": "Todos",
                      **kwargs.get("params", {})}

            async with session.get(url=url, params=params) as res:
                cls.log_response(res)

                content = (res.ok and await res.text()) or ""
                soup = BeautifulSoup(content, 'html.parser')
                trs = soup.find_all("tr", class_=re.compile(r"^L1$"))

                entries = cls.parse_entries(trs)
                cls.write_cache("entries", entries)

        if query:
            entries[:] = [e for e in entries if query in e["title"].lower()]
        else:
            entries.sort(key=lambda e: as_int(e["pack_n"]), reverse=True)
        total = len(entries)

        entries[:] = entries[start:] if all_pages else entries[start:start+length]
        showing = len(entries)

        if query:
            entries.sort(key=lambda e: e["title"].lower().find(query))

        remaining = max(0, total - (start + showing))

        return {
            "entries": entries,
            "start": start,
            "showing": showing,
            "remaining": remaining,
            "total": total,
            "parsed": True
        }

    @classmethod
    def parse_entries(cls, entries: list) -> list[dict]:

        new_entries = []

        for tag in entries:
            tds = tag.find_all("td")

            new_entries.append({
                "title": get_body(tds[4]),
                "command": get_body(tds[3]),
                "size": get_body(tds[2]),
                "gets_n": get_body(tds[1]),
                "pack_n": get_body(tds[0]),
            })

        return new_entries

    @classmethod
    def make_table(cls, data: dict) -> Table:
        t = cls._Table(data)

        t.add_column("Title")
        t.add_column("Size", justify="right", style="white")
        t.add_column("Command", style="dim")

        for cell in data['entries']:
            t.add_row(
                cell['title'],
                cell['size'],
                cell['command'],
            )

        return t


class AnimeNSK_Torrent(Queryable):

    END_POINT = "https://www.ansktracker.net/"

    @classmethod
    async def make_request(cls, query: str, **kwargs) -> dict:

        def search_total(soup: BeautifulSoup, **_) -> int:
            table = soup.find("span", class_=re.compile(r"^pager$"))
            curr_pager = table and table.find(
                "font", class_=re.compile(r"^gray$"))

            if not table:
                logging.info(
                    "search_total() returning 0 - pagers table absent")
                return 0

            def total_of(tag): return int(get_body(tag).split("-")[1])

            exp = re.compile(r"^\?.*page=(\d+).*")
            pagers = table.find_all(href=exp)
            pagers = pagers and list(
                filter(lambda p: len(get_body(p).split("-")) == 2, pagers))

            # logging.debug(f"{curr_pager = }")
            # logging.debug(f"{pagers = }")

            if not pagers:
                if curr_pager:
                    logging.info("search_total() - there's only one page")
                    return total_of(curr_pager)
                else:
                    logging.info("search_total() returning 0 - not in a page?")
                    return 0

            def search_last(a, b): return a if total_of(a) > total_of(b) else b

            if curr_pager:
                pagers.append(curr_pager)

            return total_of(reduce(search_last, pagers))

        def get_trs(soup: BeautifulSoup):
            trs = soup.find_all("tr", id=re.compile(r"^trTorrentRow$"))
            if trs:
                # Correction on the first tr
                table_teste = soup.find("table", class_=re.compile(r"^teste$"))
                cursed_tr = table_teste.find_all("tr", recursive=False)[1]
                missing_tds = cursed_tr.find_all("td", recursive=False)[2:]
                trs[0].extend(missing_tds)

            return trs

        params = {
            "search": query,
            "page": 0,

            # (None, Seeders, Leechers, Size, Downloads, Date, Name)
            "order": 5 if query else 0,

            # Types:
            "c1": 1,  # Anime
            "c2": 1,  # Anime OVA
            "c3": 1,  # Anime Movie
            # "c4": 1, # Doramas
            # "c5": 1, # Music
            # "c6": 1, # Others
            # "mult": 1, # Multiplied Upload
            # "freeleech": 1, # Free Leeching
            **kwargs.get("params", {})
        }

        return await _make_php_request(
            query=query,
            **kwargs,
            cls=cls,
            SITE_PAGE_LENGTH=15,
            params=params,
            search_total=search_total,
            get_trs=get_trs,
            needed_cookies={"pass", "uid"},
        )

    @ classmethod
    def parse_entries(cls, entries: list) -> list[dict]:
        new_entries = []

        types = {"Anime TV": "Completo",
                 "Anime OVA": "OVA",
                 "Anime Movie": "Filme"}

        for entry in entries:

            tds = entry.find_all("td")
            if len(tds) != 9:
                cls.log(
                    logging.warn, f"Skipping a entry with {len(tds)} columns instead of {9}")
                continue

            _type = get_attr(tds[0].find("img"), "alt")

            new_entries.append({
                "title": get_body(tds[1].find("a")),
                "type": types.get(_type, _type),
                "page": cls.END_POINT + get_href(tds[1].find("a")).replace("&hit=1", ""),
                "multiplier": get_body(tds[1].find("font", color="red")),
                "free_leech": get_body(tds[1].find("font", color="green")),

                "size": get_body(tds[5]),
                "seeds": as_int(get_body(tds[7])),
                "leechers": as_int(get_body(tds[8])),
                "completions": as_int(get_body(tds[6])),
                "archive_qtd": as_int(get_body(tds[2])),

                # "seeders_list_link" : "",
                # "leechers_list_link" : "",
                # "archive_list_link" : cls.END_POINT + get_href(tds[4].find("a")),
            })

        return new_entries

    @ classmethod
    def make_table(cls, data: dict) -> Table:
        t = cls._Table(data)

        t.add_column("Title")
        t.add_column("Type", justify="center")
        t.add_column("Size", justify="right", style="white")
        t.add_column("Page Link", style="dim")

        for cell in data['entries']:

            style = ""
            if cell['seeds'] == 0:
                style += " dim"

            type_style = {
                "Completo": "complete",
                "OVA": "special",
                "Filme": "movie",
            }.get(cell['type'], "white")

            t.add_row(
                (
                    with_style(cell['free_leech'], "spring_green3 bold") +
                    with_style(cell['multiplier'], "indian_red1 bold") +
                    cell['title']
                ),
                with_style(cell['type'], type_style),
                cell['size'],
                as_link(cell['page']),
                style=style
            )

        return t
