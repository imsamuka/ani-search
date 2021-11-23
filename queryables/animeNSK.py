from queryables.queryable import *


class AnimeNSK_Packs(Queryable):

    END_POINT = "https://packs.ansktracker.net/"

    @classmethod
    def make_request(cls, query: str, all_pages=False, page=0, length=25, **kwargs) -> dict:
        entries = kwargs.get("entries", [])

        start = page * length

        url = cls.END_POINT + "index.php"
        params = {"Modo": "Busca", "find": query} if query else {
            "Modo": "Packs", "bot": "Todos"}

        res = requests.get(url, params)
        content = (res and (res.status_code == 200)
                   and res.content) or "<html></html>"

        trs = BeautifulSoup(content, 'html.parser').find_all(
            "tr", class_=re.compile(r"^L1$"))

        entries.extend(trs[start:] if all_pages else trs[start:start+length])

        total = len(trs)
        showing = len(entries)
        remaining = total - (start + showing)
        if remaining < 0:
            remaining = 0

        cls.log_response(res, page, total, remaining)

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
