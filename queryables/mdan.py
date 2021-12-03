from queryables.queryable import *
from queryables.queryable import _make_php_request


class MDAN(Queryable):

    END_POINT = "https://bt.mdan.org/"

    @classmethod
    async def make_request(cls, query: str, **kwargs) -> dict:

        def search_total(soup: BeautifulSoup, trs: list[Tag]) -> int:
            curr_page_qtd = len(trs)
            table = soup.find("table", "main", align="center")
            curr_pager = table and table.find("td", class_="highlight")

            if not table or not curr_pager:
                return curr_page_qtd  # not in a page, curr_page_qtd probably 0

            exp = re.compile(r"^browse\.php\?.*page=(\d+).*")
            pagers = table.find_all(
                href=exp,
                title=lambda t: t and len(t.split("-")) == 2
            )

            if not pagers:
                return curr_page_qtd  # there's only one page

            def pager_i(tag): return int(exp.search(tag.get("href")).group(1))
            def search_last(a, b): return a if pager_i(a) > pager_i(b) else b

            last_pager = reduce(search_last, pagers)
            last_pager_total = int(last_pager.get("title").split("-")[1])
            last_pager_i = pager_i(last_pager)

            current_pager_i = as_int(curr_pager.string) - 1

            return last_pager_total + (curr_page_qtd if last_pager_i <= current_pager_i else 0)

        def get_trs(soup: BeautifulSoup):
            return soup.find_all("tr", class_=re.compile(r"^browse_color$"))

        params = {
            "cats1[]": [1, 2, 5],  # Animes
            "cats2[]": 3,  # Movies
            "page": 0,
            "search": query,
            "searchin": "title" or "all",  # Maybe set as kwargs option
            "incldead": 0,  # No dead torrents
            # "only_free":1, # Salva-ratio
            # "only_silver":2, # Silver
            **kwargs.get("params", {})
        }

        return await _make_php_request(
            query=query,
            **kwargs,
            cls=cls,
            SITE_PAGE_LENGTH=30,
            params=params,
            search_total=search_total,
            get_trs=get_trs,
            needed_cookies={"pass", "hashv", "uid"},
        )

    @classmethod
    def parse_entries(cls, entries: list) -> list[dict]:
        '''
        <tr class="browse_color">
            <td><a href="browse.php?cat=5"><img alt="Completo" src="./pic/caticons/1/completo.gif"/></a></td>
            <td>
                    <a href="details.php?id=4012&amp;hit=1"><b>[OldAge] Mushishi - 01-26 [BD]</b></a>
                <br><a id="torrenth" href="#"><img src="./pic/free.gif"><span>Até dia: 24-11-2021<br>(2d 09:07:54 faltando)<br></span></a>
            </td>
            <td>
                  <b><a href="peerlist.php?id=4012#seeders"><font color="#006600">15</font></a></b>
                / <b><a href="peerlist.php?id=4012#leechers">0</a></b>
            </td>
            <td>93 vezes</td>
            <td><b><a href="filelist.php?id=4012">26</a></b></td>
            <td>25.35<br/>GB</td>
            <td><span>11:10<br/>09-09-2021</span></td>
            <td><a href="userdetails.php?id=108770"><b>Soma</b></a></td>
        </tr>
        '''

        def separate(lst): return (lst and (len(lst) == 3)
                                   and lst[0].strip() + ' ' + lst[2].strip()) or ''

        new_entries = []
        for cell in entries:

            tds = cell.find_all("td")

            if len(tds) != 8:
                cls.log(
                    logging.warn, f"Skipping a entry with {len(tds)} columns instead of {8}")
                logging.debug(cell)
                continue

            bs = tds[2].find_all("b")
            if len(bs) != 2:
                cls.log(logging.warn, f"Found a probably invalid entry")
                logging.debug(cell)

            new_entries.append({
                "title": get_body(tds[1].find("b")),
                "page": cls.END_POINT + get_href(tds[1].find("a")).replace("&hit=1", ""),
                "type": get_attr(tds[0].find("img"), "alt"),

                "date": separate(list(tds[6].find("span").children)),
                "silver": False,  # There's no example to use
                "salva_ratio": bool(tds[1].find("a", id="torrenth")),

                "seeds": as_int(get_body(bs[0].find("font"))) if 0 < len(bs) else 0,
                "leechers": as_int(get_body(bs[1].find("a"))) if 1 < len(bs) else 0,
                "completions": as_int(get_body(tds[3])),
                "size": separate(list(tds[5].children)),
                "archive_qtd": as_int(get_body(tds[4].find("a"))),

                # "seeders_list_link" : "",
                # "leechers_list_link" : "",
                # "archive_list_link" : cls.END_POINT + get_href(tds[4].find("a")),

                "uploader_name": get_body(tds[7].find("b")),
                "uploader_link": cls.END_POINT + get_href(tds[7].find("a")),
            })
        return new_entries

    @classmethod
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
                "Episódios": "episodes",
                "Completo": "complete",
                "OVAs": "special",
                "Filmes": "movie",
            }.get(cell['type'], "white")

            t.add_row(
                cell['title'],
                with_style(cell['type'], type_style),
                cell['size'],
                as_link(cell['page']),
                style=style
            )

        return t
