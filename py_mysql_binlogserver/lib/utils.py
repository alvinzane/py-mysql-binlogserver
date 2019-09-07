import re


def normalize_query(query):
    query = query.strip()

    if "=>" not in query:
        query += " => main"
    match = re.search('(?P<q_type>[a-zA-X]+)(?P<q_text>\s.*)=>(?P<pip_name>.*)', query)
    pip_name = match.group('pip_name')
    if not pip_name:
        pip_name = None
    options = re.split('\s+', query)
    return match.group('q_type'), match.group('q_type') + match.group('q_text').rstrip(), pip_name.strip(), options[1:]


def pipe_query(query):

    pipe_query_list = {
        "show servers": "select pipe_name,server_host,server_port,server_user from mysql_servers",
        "show users": "select user_id,user_name from mysql_users",
        "show helps": "select * from mysql_helps",
        "select @@version_comment limit 1": "select '(MySQL-Piper GPL)' as version_comment",
        "show history": "select id,user_id,server_id,command_text from com_history order by id desc limit 10",
    }
    if query in pipe_query_list.keys():
        query = pipe_query_list[query]

    return query in pipe_query_list.keys(), query
