"""Données JSON de l'éditeur de planning interactif."""
import site_settings

from .optimiseur import generer_planning_excel


def get_planning_data_for_editor_v2(target_date):
    """
    Version qui utilise directement la génération normale avec return_data_only=True
    mais en corrigeant le problème de clés.
    """
    try:
        print(f"🔧 [EDITOR] Début génération du planning - Date: {target_date}")
        
        # Retourner à la méthode return_data_only=True mais avec les corrections
        print(f"📞 [EDITOR] Appel de generer_planning_excel avec return_data_only=True")
        success, result = generer_planning_excel(target_date, return_data_only=True)
        print(f"📋 [EDITOR] Retour de generer_planning_excel: success={success}")
        
        if not success:
            print(f"❌ Échec de la génération: {result}")
            return {
                'courses': [],
                'days': [target_date],
                'time_slots': site_settings.get_time_layout()['slots'],
                'assignments': {},
                'rooms': [],
                'error': result
            }

        print(f"✅ Planning avec assignations généré avec succès")
        return result

    except Exception as e:
        print(f"❌ Erreur dans get_planning_data_for_editor_v2: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'courses': [],
            'days': [target_date],
            'time_slots': site_settings.get_time_layout()['slots'],
            'assignments': {},
            'rooms': [],
            'error': str(e)
        }
