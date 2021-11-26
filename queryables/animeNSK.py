from queryables.queryable import *


class AnimeNSK_Packs(Queryable):

    END_POINT = "https://packs.ansktracker.net/"

    @classmethod
    def make_request(cls, query: str, all_pages=False, page=0, length=30, **kwargs) -> dict:
        entries = cls.read_cache("entries") or []
        start = page * length

        if not entries:
            url = cls.END_POINT + "index.php"
            params = {"Modo": "Packs", "bot": "Todos"}

            res = requests.get(url, {**params, **kwargs.get("params", {})})
            cls.log_response(res, page)

            soup = get_res_soup(res)
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
    def make_request(cls, query: str, all_pages=False, page=0, length=30, **kwargs) -> dict:

        def search_total(soup: BeautifulSoup) -> int:
            table = soup.find("span", class_=re.compile(r"^pager$"))
            curr_pager = table and table.find(
                "font", class_=re.compile(r"^gray$"))

            if not table or not curr_pager:
                return 0  # not in a page?

            def total_of(tag): return int(get_body(tag).split("-")[1])

            exp = re.compile(r"^\?.*page=(\d+).*")
            pagers = table.find_all(href=exp)
            pagers = pagers and list(
                filter(lambda p: len(get_body(p).split("-")) == 2, pagers))

            # logging.debug(f"{curr_pager = }")
            # logging.debug(f"{pagers = }")

            if not pagers:
                return total_of(curr_pager)  # there's only one page

            def search_last(a, b): return a if total_of(a) > total_of(b) else b

            pagers.append(curr_pager)

            return total_of(reduce(search_last, pagers))

        def correct_first_tr(soup: BeautifulSoup, tr: Tag) -> Tag:
            table_teste = soup.find("table", class_=re.compile(r"^teste$"))
            cursed_tr = table_teste.find_all("tr", recursive=False)[1]
            missing_tds = cursed_tr.find_all("td", recursive=False)[2:]

            tr.extend(missing_tds)

        SITE_PAGE_LENGTH = 15

        start = page * length
        site_page = (start + kwargs.get("showing", 0)) // SITE_PAGE_LENGTH
        site_start = 0 if ("rec_start" in kwargs) else start % SITE_PAGE_LENGTH

        url = cls.END_POINT + "browse.php"
        params = {
            "search": query,
            "page": site_page,

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
        }

        cookies = kwargs.get("cookies", {})
        cls.raise_if_missing_cookies(cookies, {"pass", "uid"})

        res = requests.get(
            url, {**params, **kwargs.get("params", {})}, cookies=cookies)
        cls.log_response(res, page)

        soup = get_res_soup(res)

        cls.raise_if_expired_cookies(
            soup.find("form", action="takelogin.php", method="post"))

        # logging.debug(soup.prettify())

        trs = soup.find_all("tr", id=re.compile(r"^trTorrentRow$"))

        if trs:
            correct_first_tr(soup, trs[0])

        entries = kwargs.get("entries", [])
        entries.extend(trs[site_start:])

        if not all_pages:
            del entries[length:]

        showing = len(entries)
        total = max(search_total(soup), len(trs), showing)

        remaining = max(0, total - (start + showing))

        if res.status_code == 200 and remaining and (all_pages or showing < length):
            sleep(0.1)  # Avoid DDOS

            return cls.make_request(
                query=query, all_pages=all_pages, page=page, length=length,
                **{**kwargs,
                    'entries': entries,
                    'rec_start': kwargs.get("rec_start", start),
                    'showing': showing,
                   }
            )

        return {
            "entries": entries,
            "start": kwargs.get("rec_start", start),
            "showing": showing,
            "remaining": remaining,
            "total": total,
        }

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
