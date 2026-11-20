"""Import every model module so Base.metadata is complete (used by Alembic and create_all)."""
from app.db.base import Base  # noqa: F401
from app.modules.auth_rbac import models as auth_models  # noqa: F401
from app.modules.availability_verify import models as availability_models  # noqa: F401
from app.modules.comm_cert import models as comm_models  # noqa: F401
from app.modules.dms_files import models as dms_models  # noqa: F401
from app.modules.ftc import models as ftc_models  # noqa: F401
from app.modules.master_registry import models as master_models  # noqa: F401
from app.modules.message_alerts import models as alert_models  # noqa: F401
from app.modules.mis_reporting import models as mis_models  # noqa: F401
from app.modules.outage_coord import models as outage_models  # noqa: F401
from app.modules.portal_cms import models as portal_models  # noqa: F401
from app.modules.protection_tripping import models as protection_models  # noqa: F401
from app.modules.realtime_outage import models as realtime_models  # noqa: F401
from app.modules.registration import models as registration_models  # noqa: F401
from app.modules.sps_status import models as sps_models  # noqa: F401
from app.modules.ticketing_cas import models as cas_models  # noqa: F401
from app.modules.workflow_engine import models as workflow_models  # noqa: F401
