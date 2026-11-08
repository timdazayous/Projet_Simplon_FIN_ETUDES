-- Compte MariaDB en lecture seule pour l'extraction des tickets GLPI (Issue #53).
--
-- Principe du moindre privilège : ce compte ne peut que LIRE, et seulement les tables
-- utiles à l'extraction. Il ne voit pas les autres tables de GLPI (mots de passe des
-- utilisateurs, jetons, configuration...).
--
-- Le nom du compte et son mot de passe ne sont JAMAIS écrits dans ce fichier : le script
-- scripts/create_glpi_reader.py les lit dans .env et les transmet par l'entrée standard de
-- `mariadb`, sous forme de variables de session (@reader_user, @reader_password, @reader_db).
-- Le script est rejouable : relancé, il met à jour le mot de passe et les droits.
--
-- À exécuter avec le compte administrateur de MariaDB, une seule fois, par le développeur.

SET @reader_host = '%';
SET @reader_db_q = CONCAT('`', REPLACE(@reader_db, '`', '``'), '`');
-- '%' parce que, vu depuis le conteneur, le client arrive avec l'adresse de la passerelle
-- Docker et non 127.0.0.1. Le port 3307 n'est de toute façon publié que sur 127.0.0.1.

-- 1. Création du compte (ou mise à jour du mot de passe s'il existe déjà), 2 connexions au plus.
EXECUTE IMMEDIATE CONCAT(
    'CREATE USER IF NOT EXISTS ', QUOTE(@reader_user), '@', QUOTE(@reader_host),
    ' IDENTIFIED BY ', QUOTE(@reader_password), ' WITH MAX_USER_CONNECTIONS 2');
EXECUTE IMMEDIATE CONCAT(
    'ALTER USER ', QUOTE(@reader_user), '@', QUOTE(@reader_host),
    ' IDENTIFIED BY ', QUOTE(@reader_password), ' WITH MAX_USER_CONNECTIONS 2');

-- 2. Droits : SELECT uniquement, table par table (jamais `glpi`.*).
EXECUTE IMMEDIATE CONCAT(
    'GRANT SELECT ON ', @reader_db_q, '.glpi_tickets TO ',
    QUOTE(@reader_user), '@', QUOTE(@reader_host));
EXECUTE IMMEDIATE CONCAT(
    'GRANT SELECT ON ', @reader_db_q, '.glpi_itilcategories TO ',
    QUOTE(@reader_user), '@', QUOTE(@reader_host));
EXECUTE IMMEDIATE CONCAT(
    'GRANT SELECT ON ', @reader_db_q, '.glpi_entities TO ',
    QUOTE(@reader_user), '@', QUOTE(@reader_host));
EXECUTE IMMEDIATE CONCAT(
    'GRANT SELECT ON ', @reader_db_q, '.glpi_itilfollowups TO ',
    QUOTE(@reader_user), '@', QUOTE(@reader_host));
EXECUTE IMMEDIATE CONCAT(
    'GRANT SELECT ON ', @reader_db_q, '.glpi_tickets_users TO ',
    QUOTE(@reader_user), '@', QUOTE(@reader_host));
-- Table des utilisateurs : trois colonnes seulement (jamais le hachage du mot de passe,
-- ni les jetons d'API, ni les adresses). Les noms ne servent qu'à les masquer dans les textes.
EXECUTE IMMEDIATE CONCAT(
    'GRANT SELECT (id, firstname, realname) ON ', @reader_db_q, '.glpi_users TO ',
    QUOTE(@reader_user), '@', QUOTE(@reader_host));

-- 3. Contrôle : doit afficher uniquement des lignes GRANT SELECT.
EXECUTE IMMEDIATE CONCAT('SHOW GRANTS FOR ', QUOTE(@reader_user), '@', QUOTE(@reader_host));
