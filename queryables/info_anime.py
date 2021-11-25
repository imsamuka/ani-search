from queryables.queryable import *


class Info_Anime(Queryable):

    END_POINT = "https://www.infoanime.com.br/"

    @classmethod
    def make_request(cls, query: str, all_pages=False, page=0, length=30, **kwargs) -> dict:
        start = page * length
        links = cls.read_cache("all")

        if not links:
            url = cls.END_POINT + "/listageral"

            res = requests.get(url, kwargs.get("params", {}))
            cls.log_response(res, page)

            soup = get_res_soup(res)

            ul = soup.find(id="myUL")
            all_links = ul.find_all("a", href=re.compile(r"^dados\?obra="))

            links = {get_body(a): cls.END_POINT + get_href(a)
                     for a in all_links}

            cls.write_cache("all", links)

        entries = kwargs.get("entries", [])

        if query:
            filtered = [l for l in links.items() if query in l[0].lower()]
        else:
            filtered = list(links.items())

        entries.extend(filtered[start:]
                       if all_pages else filtered[start:start+length])

        if query:
            entries.sort(key=lambda e: e[0].lower().find(query))

        total = len(filtered)
        showing = len(entries)
        remaining = total - (start + showing)
        if remaining < 0:
            remaining = 0

        return {
            "entries": entries,
            "start": start,
            "showing": showing,
            "remaining": remaining,
            "total": total,
        }

    @classmethod
    def parse_entries(cls, entries: list) -> list[dict]:
        new_entries = []
        for cell in entries:
            new_entries.append({
                "title": cell[0],
                "page": cell[1],
            })
        return new_entries

    @classmethod
    def make_table(cls, data: dict) -> Table:
        t = cls._Table(data)

        t.add_column("Title")
        t.add_column("Page Link", style="dim")

        for cell in data['entries']:
            t.add_row(
                cell['title'],
                cell['page'],
            )

        return t
