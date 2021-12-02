from queryables.queryable import *


class Uniotaku(Queryable):

    END_POINT = "https://tracker.uniotaku.com/"

    @classmethod
    async def make_request(cls, query: str, all_pages=False, page=0, length=30, **kwargs) -> dict:

        start = page * length + kwargs.get("rec_start", 0)

        if all_pages and length != 1000:
            length = 1000
            page = 0

        url = cls.END_POINT + "torrents_.php"
        params = {
            "start": start,
            "length": length,

            # Filters
            # "categoria": 0,
            # "grupo": 0,
            # "status": 0,
            "ordenar": 7 if query else 0,  # Sort by More Completions
            "search[value]": query,
            "search[regex]": "false",
        }
        res = requests.get(url, {**params, **kwargs.get("params", {})})
        cls.log_response(res, page)

        j = get_res_json(res)

        entries = kwargs.get("entries", [])
        entries.extend(j.get("data", ()))
        showing = len(entries)

        total = max(showing, j.get("recordsFiltered", 0))
        remaining = max(0, total - (kwargs.get("rec_start", start) + showing))

        if res.status_code == 200 and remaining and (all_pages or showing < length):
            sleep(0.1)  # Avoid DDOS
            return await cls.make_request(
                page=page+1,
                query=query, all_pages=all_pages, length=length,
                **{**kwargs,
                    'entries': entries,
                    'rec_start': kwargs.get("rec_start", start),
                   }
            )

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
        for cell in entries:
            # '<a target="_blank" href="torrents-details.php?id=3681">Kakyuusei (1999) + Especial + OST</a>  <img class='tipr' title='Gold Coin' src='images/free.gif' border='0' alt='' />'
            torrent = get_tag(cell[0], "a")
            coin = get_tag(cell[0], "img")

            # '<img border="0" src="./images/categories/completo.png" alt="Anime Completo ">'
            _type = get_attr(get_tag(cell[1], "img"), "alt")
            if _type == "Anime Completo":
                _type = "Completo"
            if _type == "Anime":
                _type = "Episodios"

            # '<a href="https://www.tenroufansub.com/2018/05/fairy-tail-final-series.html" target="_blank"><i class="fas fa-lg fa-fw m-r-10 fa-download"></i></a>'
            external_link = get_tag(cell[2], "a")

            # '<a target="_blank" href="https://tracker.uniotaku.com/teams-view.php?id=41">Tenrou Fansub</a>'
            group = get_tag(cell[7], "a")

            # '<a href="account-details.php?id=13668">1qwertyuiop</a>'
            uploader = get_tag(cell[8], "a")

            new_entries.append({
                "title": get_body(torrent),
                "page": cls.END_POINT + get_href(torrent),
                "coin": get_attr(coin, "title"),

                "type": _type,
                "external_link": get_href(external_link),

                "seeds": int(cell[3] or 0),
                "leechers": int(cell[4] or 0),
                "completions": int(cell[5] or 0),
                "size": cell[6],

                "group_name": get_body(group),
                "group_link": get_href(group),

                "uploader_name": get_body(uploader),
                "uploader_link": cls.END_POINT + get_href(uploader),
            })

        return new_entries

    @classmethod
    def make_table(cls, data: dict) -> Table:
        t = cls._Table(data)

        t.add_column("Title")
        t.add_column("Type", justify="center", style="")
        t.add_column("Page Link", style="dim")
        t.add_column("Size", justify="right", style="white")
        t.add_column("Fansub", style="cyan", justify="center")

        for cell in data['entries']:

            style = {
                "Gold Coin": "bright_yellow",
                "Silver Coin": "light_sky_blue1",
            }.get(cell['coin'], "")

            if cell['seeds'] == 0:
                style += " dim"

            type_style = {
                "Episodios": "episodes",
                "Completo": "complete",
                "OVA": "special",
                "Filme": "movie",
                "Hentai": "nsfw",
            }.get(cell['type'], "white")

            t.add_row(
                cell['title'],
                with_style(cell['type'], type_style),
                as_link(cell['page']),
                cell['size'],
                cell['group_name'],
                style=style,
            )

        del t.columns[3]  # Delete Size column

        return t
