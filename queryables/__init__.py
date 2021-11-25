from queryables.queryable import Queryable

from queryables.info_anime import Info_Anime
from queryables.animeNSK import AnimeNSK_Packs, AnimeNSK_Torrent
from queryables.uniotaku import Uniotaku
from queryables.mdan import MDAN

from enum import Enum

queryables_list = (Info_Anime, AnimeNSK_Packs,
                   AnimeNSK_Torrent, Uniotaku, MDAN)
queryables_dict = {q.__name__: q for q in queryables_list}
queryables_enum = Enum(
    'Queryables', {str(i): q.__name__ for i, q in enumerate(queryables_list)})
