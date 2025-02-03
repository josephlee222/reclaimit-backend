import boto3
import pymysql
import sys
import logging
import json
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration (consider moving to environment variables or config file)
CONFIG = {
    'app_name': 'tester',
    'region': 'us-east-1',
    'init_username': 'admin',
    'init_password': 'Admin123%',
    'db_host': 'midori-db.czq2gkq0uuty.us-east-1.rds.amazonaws.com',
    'db_user': 'admin',
    'db_password': 'Admin123',
    'sql_file': 'deployer.sql',
    'admin_email': 'admin@admin.com'
}

# Resource trackers
RESOURCES = {
    'sqs_url': None,
    'ssm_prefix': None,
    'cognito_pool_id': None,
    'cognito_client_id': None,
    'cognito_identities_pool_id': None,
    's3_bucket_name': None
}


def handle_aws_error(func):
    """Decorator for AWS client error handling"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            logger.error(f"AWS API error in {func.__name__}: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            sys.exit(1)

    return wrapper


@handle_aws_error
def create_sqs():
    """Create SQS queue with proper configuration"""
    sqs = boto3.client('sqs', region_name=CONFIG['region'])
    queue_name = f"{CONFIG['app_name']}-queue"

    # Check if queue exists
    try:
        response = sqs.get_queue_url(QueueName=queue_name)
        RESOURCES['sqs_url'] = response['QueueUrl']
        logger.info(f"SQS queue already exists: {RESOURCES['sqs_url']}")
        return
    except sqs.exceptions.QueueDoesNotExist:
        pass

    response = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            'VisibilityTimeout': '60',
            'MessageRetentionPeriod': '86400'
        }
    )
    RESOURCES['sqs_url'] = response['QueueUrl']
    logger.info(f"Created SQS queue: {RESOURCES['sqs_url']}")


@handle_aws_error
def create_s3():
    """Create S3 bucket with proper region handling"""
    s3 = boto3.client('s3', region_name=CONFIG['region'])
    # Randomize bucket name
    bucket_name = f"{CONFIG['app_name']}-bucket-{CONFIG['region']}".lower() + ''.join([str(i) for i in range(10)])
    RESOURCES['s3_bucket_name'] = bucket_name

    # Check if bucket exists
    try:
        s3.head_bucket(Bucket=bucket_name)
        logger.info(f"S3 bucket already exists: {bucket_name}")
        return
    except ClientError:
        pass

    create_args = {'Bucket': bucket_name}
    if CONFIG['region'] != 'us-east-1':
        create_args['CreateBucketConfiguration'] = {
            'LocationConstraint': CONFIG['region']
        }

    s3.create_bucket(**create_args)
    s3.put_object(Bucket=bucket_name, Key='items/')

    # Disable block all public access
    s3.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': False,
            'IgnorePublicAcls': False,
            'BlockPublicPolicy': False,
            'RestrictPublicBuckets': False
        }
    )

    # Enable public read access in the items folder
    s3.put_bucket_policy(
        Bucket=bucket_name,
        Policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/items/*"
                }
            ]
        })
    )
    logger.info(f"Created S3 bucket: {bucket_name}")


@handle_aws_error
def create_cognito():
    """Create Cognito resources with proper configuration"""
    idp = boto3.client('cognito-idp', region_name=CONFIG['region'])
    identity = boto3.client('cognito-identity', region_name=CONFIG['region'])

    # Create user pool with username configuration
    pool_response = idp.create_user_pool(
        PoolName=f"{CONFIG['app_name']}-user-pool",
        Policies={
            'PasswordPolicy': {
                'MinimumLength': 8,
                'RequireUppercase': True,
                'RequireLowercase': True,
                'RequireNumbers': True,
                'RequireSymbols': True
            }
        },
        # Remove UsernameAttributes and use AliasAttributes instead
        AliasAttributes=["email"],  # Empty list means username-only authentication
        Schema=[{
            'Name': 'name',
            'AttributeDataType': 'String',
            'Required': True,
            'Mutable': True
        }],
        UsernameConfiguration={
            'CaseSensitive': False  # Optional: Makes usernames case-insensitive
        }
    )
    RESOURCES['cognito_pool_id'] = pool_response['UserPool']['Id']

    # Configure MFA for only authenticator apps (TOTP)
    idp.set_user_pool_mfa_config(
        MfaConfiguration='OPTIONAL',
        UserPoolId=RESOURCES['cognito_pool_id'],
        SoftwareTokenMfaConfiguration={
            'Enabled': True
        },
    )

    logger.info(f"Created Cognito User Pool: {RESOURCES['cognito_pool_id']}")

    # Create a user pool group for admins
    idp.create_group(
        UserPoolId=RESOURCES['cognito_pool_id'],
        GroupName='Admin'
    )

    logger.info("Created Cognito User Pool group: Admin")

    # Create user pool client
    client_response = idp.create_user_pool_client(
        UserPoolId=RESOURCES['cognito_pool_id'],
        ClientName=f"{CONFIG['app_name']}-client",
        GenerateSecret=False,
        RefreshTokenValidity=30,
        AccessTokenValidity=1,
        IdTokenValidity=1,
        TokenValidityUnits={
            'AccessToken': 'days',
            'IdToken': 'days',
            'RefreshToken': 'days'
        },
        ExplicitAuthFlows=[
            'ALLOW_ADMIN_USER_PASSWORD_AUTH',
            'ALLOW_USER_SRP_AUTH',
            'ALLOW_REFRESH_TOKEN_AUTH'
        ]
    )
    RESOURCES['cognito_client_id'] = client_response['UserPoolClient']['ClientId']
    logger.info(f"Created Cognito Client: {RESOURCES['cognito_client_id']}")

    # Create identity pool
    identity_response = identity.create_identity_pool(
        IdentityPoolName=f"{CONFIG['app_name']}-identity-pool",
        AllowUnauthenticatedIdentities=False,
        CognitoIdentityProviders=[{
            'ClientId': RESOURCES['cognito_client_id'],
            'ProviderName': f"cognito-idp.{CONFIG['region']}.amazonaws.com/{RESOURCES['cognito_pool_id']}"
        }]
    )

    RESOURCES['cognito_identities_pool_id'] = identity_response['IdentityPoolId']
    logger.info(f"Created Identity Pool: {RESOURCES['cognito_identities_pool_id']}")

    # Create IAM Role for authenticated users
    role_name = f"{CONFIG['app_name']}-Cognito-Authenticated-Role"
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": "cognito-identity.amazonaws.com"
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": RESOURCES['cognito_identities_pool_id']
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    }
                }
            }
        ]
    }

    iam = boto3.client('iam')

    # Create the IAM Role
    try:
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description="Role for authenticated users in the Cognito Identity Pool"
        )
        role_arn = role_response['Role']['Arn']
        logger.info(f"Created IAM Role: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        logger.info(f"IAM Role {role_name} already exists")
        role_arn = f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/{role_name}"

    # Attach the custom policy to the role
    custom_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "cognito-identity:GetCredentialsForIdentity"
                ],
                "Resource": [
                    "*"
                ]
            }
        ]
    }

    policy_name = f"{CONFIG['app_name']}-Cognito-Authenticated-Policy"
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(custom_policy)
        )
        logger.info(f"Attached policy {policy_name} to role {role_name}")
    except Exception as e:
        logger.error(f"Failed to attach policy: {e}")
        raise

    # Set roles for the identity pool
    identity.set_identity_pool_roles(
        IdentityPoolId=RESOURCES['cognito_identities_pool_id'],
        Roles={
            'authenticated': role_arn
        }
    )
    logger.info(f"Set Identity Pool roles for {RESOURCES['cognito_identities_pool_id']}")

    # Create admin user
    try:
        idp.admin_create_user(
            UserPoolId=RESOURCES['cognito_pool_id'],
            Username=CONFIG['init_username'],
            UserAttributes=[
                {'Name': 'email', 'Value': CONFIG['admin_email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'name', 'Value': 'Admin'}
            ],
            TemporaryPassword=CONFIG['init_password'],
            MessageAction='SUPPRESS'
        )
        logger.info("Created admin user")
    except idp.exceptions.UsernameExistsException:
        logger.warning("Admin user already exists")

    # Add admin user to admin group
    idp.admin_add_user_to_group(
        UserPoolId=RESOURCES['cognito_pool_id'],
        Username=CONFIG['init_username'],
        GroupName='Admin'
    )


@handle_aws_error
def create_db():
    """Initialize database schema"""
    try:
        # Create database
        conn = pymysql.connect(
            host=CONFIG['db_host'],
            user=CONFIG['db_user'],
            password=CONFIG['db_password'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {CONFIG['app_name']}")
            logger.info(f"Database {CONFIG['app_name']} created or exists")

            cursor.execute(f"USE {CONFIG['app_name']}")
            with open(CONFIG['sql_file'], 'r') as f:
                sql = f.read()
                for statement in sql.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
            logger.info("SQL schema executed successfully")

        conn.commit()
    except pymysql.Error as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()


@handle_aws_error
def create_ssm():
    """Store configuration in SSM Parameter Store"""
    ssm = boto3.client('ssm', region_name=CONFIG['region'])
    prefix = f"/{CONFIG['app_name']}/"
    RESOURCES['ssm_prefix'] = prefix

    parameters = {
        'rds_host': CONFIG['db_host'],
        'rds_user': CONFIG['db_user'],
        'rds_password': CONFIG['db_password'],
        'db_name': CONFIG['app_name']
    }

    for name, value in parameters.items():
        ssm.put_parameter(
            Name=f"{prefix}{name}",
            Value=value,
            Type='SecureString' if 'password' in name else 'String',
            Overwrite=True
        )
    logger.info("SSM parameters created/updated")


def main():
    """Main deployment workflow"""
    logger.info("Starting deployment...")
    create_sqs()
    create_s3()
    create_cognito()
    create_db()
    create_ssm()

    logger.info("\nDeployment completed successfully!")
    print(f"SQS URL: {RESOURCES['sqs_url']}")
    print(f"SSM Prefix: {RESOURCES['ssm_prefix']}")
    print(f"Cognito Pool ID: {RESOURCES['cognito_pool_id']}")
    print(f"Cognito Client ID: {RESOURCES['cognito_client_id']}")
    print(f"Identity Pool ID: {RESOURCES['cognito_identities_pool_id']}")
    print(f"S3 Bucket: {RESOURCES['s3_bucket_name']}")


if __name__ == "__main__":
    main()