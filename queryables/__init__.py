from queryables.queryable import Queryable

from queryables.uniotaku import Uniotaku
from queryables.mdan import MDAN
from queryables.animeNSK import AnimeNSK_Packs, AnimeNSK_Torrent
from queryables.info_anime import Info_Anime

from enum import Enum

queryables_list = (Uniotaku, MDAN, AnimeNSK_Packs,
                   AnimeNSK_Torrent, Info_Anime)
queryables_dict = {q.__name__: q for q in queryables_list}
queryables_enum = Enum(
    'Queryables', {str(i): q.__name__ for i, q in enumerate(queryables_list)})
