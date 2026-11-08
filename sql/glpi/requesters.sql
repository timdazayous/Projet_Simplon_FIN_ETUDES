-- Demandeurs des tickets extraits (Issue #53, compétence C2).
-- Le marqueur {ids} est remplacé par le script par une liste de marqueurs %s (un par ticket,
-- jamais par les valeurs) ; les identifiants sont liés par le pilote.
--
-- type = 1 : demandeur (2 = technicien assigné, 3 = observateur : inutiles ici).
-- LEFT JOIN : un demandeur sans compte (adresse seule, users_id = 0) reste visible par son
--   alternative_email. Colonnes lues dans glpi_users : id, firstname, realname seulement (le
--   compte en lecture seule n'a pas le droit d'en lire d'autres) ; les noms ne servent qu'à
--   masquer le texte libre, ils ne sont jamais écrits.
-- Index utilisé : la clé unique (tickets_id, type, users_id, alternative_email).
SELECT
    tu.tickets_id,
    tu.users_id,
    tu.alternative_email,
    u.firstname,
    u.realname
FROM glpi_tickets_users AS tu
LEFT JOIN glpi_users AS u ON u.id = tu.users_id
WHERE tu.type = 1
  AND tu.tickets_id IN ({ids})
