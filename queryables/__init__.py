from queryables.queryable import Queryable

from queryables.uniotaku import Uniotaku
from queryables.mdan import MDAN

from enum import Enum

queryables_list = (Uniotaku, MDAN)
queryables_dict = {q.__name__: q for q in queryables_list}
queryables_enum = Enum(
    'Queryables', {str(i): q.__name__ for i, q in enumerate(queryables_list)})
