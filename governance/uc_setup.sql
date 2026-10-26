-- Unity Catalog setup for the intake demo. Run by ops/run.py uc-sql <file> <section>.
-- ${catalog} is replaced from the INTAKE_CATALOG env var / bundle variable.

-- @section bootstrap
CREATE SCHEMA IF NOT EXISTS ${catalog}.raw COMMENT 'Landing files and Lakebase change history (bronze inputs)';
CREATE SCHEMA IF NOT EXISTS ${catalog}.silver COMMENT 'Cleaned and AI-enriched intake requests';
CREATE SCHEMA IF NOT EXISTS ${catalog}.gold COMMENT 'Governed portfolio tables and metric views for leadership';
CREATE SCHEMA IF NOT EXISTS ${catalog}.ops COMMENT 'Access mappings and operational config for the intake app';
CREATE VOLUME IF NOT EXISTS ${catalog}.raw.landing COMMENT 'Landing zone for synthetic opportunity log and project tracker files';
CREATE TABLE IF NOT EXISTS ${catalog}.ops.user_business_unit (
  user_email STRING NOT NULL COMMENT 'Workspace user email',
  business_unit STRING NOT NULL COMMENT 'Business unit whose rows the user may see'
) COMMENT 'Maps non task_force users to the business unit they may see through row filters';
