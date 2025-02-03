import boto3
import pymysql
import os

ssm_client = boto3.client('ssm')
prefix = os.environ.get('SSM_PREFIX')

# Batch get parameters from SSM
response = ssm_client.get_parameters(Names=[prefix + 'rds_host', prefix + 'rds_user', prefix + 'rds_password', prefix + 'db_name'], WithDecryption=True)
ssm_dict = {param['Name']: param['Value'] for param in response['Parameters']}

def create_connection():
    # RDS connection details from environment variables
    HOST = ssm_dict[prefix + 'rds_host']
    USER = ssm_dict[prefix + 'rds_user']
    PASSWORD = ssm_dict[prefix + 'rds_password']
    DB_NAME = ssm_dict[prefix + 'db_name']

    connection = pymysql.connect(host=HOST, user=USER, password=PASSWORD, database=DB_NAME, charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor, autocommit=True)

    return connection