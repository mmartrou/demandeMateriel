"""
Script de migration pour mettre à jour group_count depuis quantity
pour les anciennes demandes où group_count est à 1 par défaut
"""

from database import get_db_connection

def migrate_group_count():
    """Copier les valeurs de quantity vers group_count pour les anciennes entrées"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    # Compter combien de lignes seront affectées
    cursor.execute('SELECT COUNT(*) FROM material_requests WHERE group_count = 1 OR group_count IS NULL')
    count_result = cursor.fetchone()
    
    if isinstance(count_result, dict):
        count = count_result['count'] if 'count' in count_result else count_result.get('COUNT(*)', 0)
    else:
        count = count_result[0] if count_result else 0
    
    print(f"📊 Nombre de demandes à mettre à jour: {count}")
    
    if count == 0:
        print("✅ Aucune demande à mettre à jour.")
        conn.close()
        return
    
    # Mettre à jour group_count = quantity pour toutes les entrées où group_count est 1 ou NULL
    cursor.execute('''
        UPDATE material_requests 
        SET group_count = quantity 
        WHERE group_count = 1 OR group_count IS NULL
    ''')
    
    conn.commit()
    rows_updated = cursor.rowcount
    
    print(f"✅ Migration terminée : {rows_updated} demande(s) mise(s) à jour")
    print(f"   group_count a été copié depuis quantity")
    
    conn.close()

if __name__ == '__main__':
    print("🔧 Démarrage de la migration group_count...")
    migrate_group_count()
    print("✅ Migration terminée!")
