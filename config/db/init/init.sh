#!/bin/bash

mysql=( mysql --protocol=socket -uroot -hlocalhost --socket="${SOCKET}" -p"${MYSQL_ROOT_PASSWORD}" )

${mysql[@]} -e "CREATE DATABASE IF NOT EXISTS \`cisite\`;"
${mysql[@]} -e "CREATE DATABASE IF NOT EXISTS \`cisite_public\`;"

${mysql[@]} -e "CREATE OR REPLACE USER 'cisite'@'%' IDENTIFIED BY '${MYSQL_CISITE_PASSWORD}';"
${mysql[@]} -e "CREATE OR REPLACE USER 'cisite_public'@'%' IDENTIFIED BY '${MYSQL_CISITE_PUBLIC_PASSWORD}';"

${mysql[@]} -e "GRANT ALL ON cisite.* TO 'cisite'@'%';"
# For migrations
${mysql[@]} -e "GRANT ALL ON cisite_public.* TO 'cisite'@'%';"
${mysql[@]} -e "GRANT ALL ON cisite_public.* TO 'cisite_public'@'%';"
