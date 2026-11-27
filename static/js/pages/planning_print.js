// Actualisation automatique de la page du planning (version "affichage" projetée sur un écran, et version
// "techniciens") : quand un technicien modifie le planning dans l'éditeur, la feuille affichée se met à jour
// toute seule. Chargé sauf pour l'ouverture directe en impression, ?print=1 (voir templates/planning_print.html).
//
// Principe : on redemande toutes les INTERVALLE_MS la même adresse, on compare la feuille reçue à celle
// qui est affichée et, si elle diffère, on la remplace (sans recharger la page, donc sans clignotement).
(function () {
    const INTERVALLE_MS = 5000;

    // Pastille rouge dans le coin : cachée tant que tout va bien, affichée seulement si l'actualisation échoue
    const etat = document.getElementById('etat-maj');
    let signatureAffichee = null;
    let enCours = false;

    // Empreinte du contenu de la feuille : si elle change, le planning a changé. Le bloc ".meta" (version
    // techniciens : "Édité le <heure actuelle>") est exclu, car il change chaque minute sans que le planning
    // ait changé ; il est mis à jour en même temps que le reste quand la feuille est remplacée.
    function signature(feuille) {
        const copie = feuille.cloneNode(true);
        const meta = copie.querySelector('.meta');
        if (meta) meta.remove();
        return copie.innerHTML;
    }

    function signalerProbleme(texte) {
        if (!etat) return;
        etat.textContent = texte;
        etat.hidden = false;
    }

    function effacerProbleme() {
        if (etat) etat.hidden = true;
    }

    async function actualiser() {
        if (enCours || document.hidden) return;
        enCours = true;
        try {
            const reponse = await fetch(window.location.href, { cache: 'no-store', credentials: 'same-origin' });
            // Session expirée : le serveur renvoie vers la page de connexion. On garde le planning affiché.
            if (reponse.redirected) throw new Error('Session expirée : reconnectez-vous');
            // Pas (ou plus) de planning : en mode affichage sans date, c'est le changement de jour ; la page
            // "aucun planning" se réactualise ensuite seule toutes les minutes.
            if (reponse.status === 404) { window.location.reload(); return; }
            if (!reponse.ok) throw new Error(`Planning indisponible (erreur ${reponse.status})`);

            const doc = new DOMParser().parseFromString(await reponse.text(), 'text/html');
            const nouvelle = doc.querySelector('main.feuille');
            if (!nouvelle) throw new Error('Réponse inattendue du serveur');

            const sig = signature(nouvelle);
            if (sig !== signatureAffichee) {
                document.querySelector('main.feuille').replaceWith(document.importNode(nouvelle, true));
                signatureAffichee = sig;
            }
            effacerProbleme();
        } catch (e) {
            signalerProbleme(`⚠ ${e.message} : le planning affiché n'est peut-être plus à jour`);
        } finally {
            enCours = false;
        }
    }

    // Signature de départ : celle de la page telle que chargée (un éventuel écart de sérialisation
    // avec la première réponse provoquerait au pire un remplacement inutile, sans conséquence).
    signatureAffichee = signature(document.querySelector('main.feuille'));
    setInterval(actualiser, INTERVALLE_MS);
    // Un onglet caché ne se met pas à jour : on rattrape dès qu'il redevient visible.
    document.addEventListener('visibilitychange', () => { if (!document.hidden) actualiser(); });
})();
