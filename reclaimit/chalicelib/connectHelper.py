import boto3
import pymysql

ssm_client = boto3.client('ssm')

# Batch get parameters from SSM
response = ssm_client.get_parameters(Names=['/midori/rds_host', '/midori/rds_user', '/midori/rds_password', '/midori/db_name'], WithDecryption=True)
ssm_dict = {param['Name']: param['Value'] for param in response['Parameters']}

def create_connection():
    # RDS connection details from environment variables
    HOST = ssm_dict['/midori/rds_host']
    USER = ssm_dict['/midori/rds_user']
    PASSWORD = ssm_dict['/midori/rds_password']
    DB_NAME = ssm_dict['/midori/db_name']

    connection = pymysql.connect(host=HOST, user=USER, password=PASSWORD, database=DB_NAME, charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor, autocommit=True)

    return connection