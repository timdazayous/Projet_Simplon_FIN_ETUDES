-- Extraction incrémentale des tickets GLPI (Issue #53, compétence C2).
-- Paramètres (liés par le pilote, jamais concaténés) : %(since)s date UTC, %(limit)s entier.
--
-- Choix de sélection : seules les colonnes utiles au tri sont lues (pas de SELECT *) ;
--   l'identifiant du demandeur n'est pas ici, il vient de requesters.sql (un ticket peut avoir
--   plusieurs demandeurs : les mettre dans cette requête dupliquerait les lignes).
-- Jointures : LEFT JOIN, pour qu'un ticket sans catégorie ou d'une entité supprimée ne
--   disparaisse pas de l'extraction ; les deux jointures se font sur la clé primaire (1 ligne).
-- Filtres : is_deleted = 0 exclut les tickets mis à la corbeille ; date_mod >= since ne lit que
--   ce qui a changé depuis la dernière extraction (index `date_mod`).
-- Nombre de suivis : sous-requête corrélée, qui utilise l'index (itemtype, items_id) de
--   glpi_itilfollowups ; elle évite un GROUP BY sur le résultat de la jointure.
-- Ordre : (date_mod, id) est déterministe ; --limit prend donc toujours les plus anciens
--   changements d'abord et l'extraction suivante reprend où celle-ci s'est arrêtée.
SELECT
    t.id,
    t.date,
    t.date_mod,
    t.name,
    t.content,
    t.status,
    t.type,
    t.priority,
    t.externalid,
    c.code AS category_code,
    e.name AS entity_name,
    (
        SELECT COUNT(*)
        FROM glpi_itilfollowups AS f
        WHERE f.itemtype = 'Ticket' AND f.items_id = t.id
    ) AS followup_count
FROM glpi_tickets AS t
LEFT JOIN glpi_itilcategories AS c ON c.id = t.itilcategories_id
LEFT JOIN glpi_entities AS e ON e.id = t.entities_id
WHERE t.is_deleted = 0
  AND t.date_mod >= %(since)s
ORDER BY t.date_mod, t.id
LIMIT %(limit)s
