# Compatibility facade: crm.urls imports views from this module.
# Actual implementations are split by domain under crm.view_modules.*

from .view_modules.dashboard import *
from .view_modules.schedule import *
from .view_modules.users import *
from .view_modules.education import *
from .view_modules.finance import *
from .view_modules.sales import *
from .view_modules.messages import *
from .view_modules.tasks import *
