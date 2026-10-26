"""Accès à la base de données, découpé par thème (un module par table ou groupe de tables).

Tout est ré-exporté ici : le reste du projet continue d'écrire « from database import ... »
ou « database.xxx ». DATABASE_PATH est défini ici et relu à chaque connexion (voir connexion.py),
ce qui permet aux tests de pointer vers une base temporaire."""
import os

# Base SQLite locale (développement, ou secours sans DATABASE_URL) : data/, non versionné
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'material_requests.db')

from .connexion import (  # noqa: E402, F401
    get_db_connection,
    close_request_connection,
    _ouvrir_connexion,
)
from .schema import (  # noqa: E402, F401
    ANCIENNE_ORGANISATION_DES_SALLES,
    init_database,
    ANCIEN_COMPTE_LABO_PAR_DEFAUT,
)
from .enseignants import (  # noqa: E402, F401
    add_teacher,
    delete_teacher,
    get_all_teachers,
    update_teacher_short_name,
    get_all_levels,
    add_level,
    delete_level,
    update_level,
    find_teacher_id_by_name,
    get_user_by_email,
    upsert_user,
    pre_associate_teacher,
    delete_user,
    get_all_users,
    get_all_student_numbers,
    update_student_number,
    add_student_number,
    delete_student_number,
    get_student_count_for_teacher,
)
from .demandes import (  # noqa: E402, F401
    rien_a_preparer,
    add_material_request,
    get_material_requests,
    get_material_request_by_id,
    update_material_request,
    toggle_prepared_status,
    confirm_draft_request,
    delete_material_request,
    update_room_type,
    SYNCABLE_REQUEST_FIELDS,
    sync_field_to_related_requests,
)
from .salles import (  # noqa: E402, F401
    get_all_rooms,
    update_room,
    add_room,
    set_room_limited_availability,
    delete_room,
    reorder_rooms,
    import_rooms_from_csv_content,
    get_room_availability,
    add_room_availability,
    delete_room_availability,
)
from .plannings import (  # noqa: E402, F401
    get_planning_data,
    get_saved_planning,
    get_planning_observations,
    get_lab_test_requests,
    get_labo_observations_map,
    get_standard_occupation,
    set_standard_occupation,
)
from .jours import (  # noqa: E402, F401
    get_working_days_config,
    set_working_day_config,
    get_working_day_overrides,
    is_working_day_configured,
    delete_working_day_config,
)
from .reglages import (  # noqa: E402, F401
    DEADLINE_WORKING_DAYS_KEY,
    DEFAULT_DEADLINE_WORKING_DAYS,
    get_setting,
    clear_settings_cache,
    get_all_settings,
    set_setting,
    get_deadline_working_days,
    set_deadline_working_days,
)
from .emploi_du_temps import (  # noqa: E402, F401
    get_tp_templates,
    upsert_tp_template,
    get_tp_template_by_id,
    get_recurring_courses,
    add_recurring_course,
    delete_recurring_course,
    generate_draft_requests_for_week,
)
