"""Planning des salles : répartition des cours (OR-Tools), éditeur, export Excel et impression.

Tout est ré-exporté ici : « from planning import ... » ou « planning.xxx ».
Pour un module précis : from planning import impression."""
from .cours import (  # noqa: F401
    to_dict_request,
    duree_par_niveau,
    eleves_par_niveau,
    interval_cours,
    extract_material_needs,
    matiere_de_la_demande,
    build_course_data_entry,
    h_to_min,
    get_room_layout,
    _max_ordinateurs,
)
from .compatibilite import (  # noqa: F401
    est_disponible_aux_creneaux,
    compatible,
    find_available_rooms_for_request,
    get_new_requests_for_date,
)
from .optimiseur import (  # noqa: F401
    generer_planning_excel,
)
from .export_excel import (  # noqa: F401
    generer_excel_optimise,
    generer_excel_from_saved_planning,
)
from .editeur import (  # noqa: F401
    get_planning_data_for_editor_v2,
)
from .impression import (  # noqa: F401
    SANS_SALLE,
    build_print_model,
    libelle_date,
    rafraichir_cours,
    salles_a_jour,
)
