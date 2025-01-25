# Deploy script for midorisky to create resources in AWS:
import boto3
def create_sqs():
    # Create SQS queue if it doesn't exist
    sqs = boto3.client('sqs')
    response = sqs.create_queue(
        QueueName='reclaimit-queue',
        Attributes={
            'DelaySeconds': '5',
            'MessageRetentionPeriod': '86400'
        }
    )

    print(response)

def create_rds():
    # Create a MySQL RDS instance if it doesn't exist
    rds = boto3.client('rds')
    response = rds.create_db_instance(
        DBInstanceIdentifier='reclaimit-db',
        MasterUsername='admin',
        MasterUserPassword='Admin123',
        DBInstanceClass='db.t2.micro',
        Engine='mysql',
        AllocatedStorage=20,
        DBName='reclaimit',
        StorageType='gp2',
        BackupRetentionPeriod=7,
        MultiAZ=False,
        PubliclyAccessible=True,
        VpcSecurityGroupIds=[
            'sg-0c1e0b6c'
        ]
    )

    # Wait for the RDS instance to be available
    waiter = rds.get_waiter('db_instance_available')
    waiter.wait(DBInstanceIdentifier='reclaimit-db')

    # Get the RDS instance endpoint
    response = rds.describe_db_instances(DBInstanceIdentifier='reclaimit-db')
    endpoint = response['DBInstances'][0]['Endpoint']['Address']
    print(endpoint)

    print(response)

def create_s3():
    # Create an S3 bucket if it doesn't exist
    s3 = boto3.client('s3')
    response = s3.create_bucket(
        Bucket='reclaimit-bucket',
        CreateBucketConfiguration={
            'LocationConstraint': 'us-east-1'
        }
    )

    # Create items folder in the bucket
    response = s3.put_object(
        Bucket='reclaimit-bucket',
        Key='items/'
    )

    # Print bucket name
    print(response['Location'])

    print(response)

create_sqs()
create_rds()
create_s3()