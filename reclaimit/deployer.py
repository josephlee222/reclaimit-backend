# Deploy script for midorisky to create resources in AWS:
import boto3
def create_sqs():
    # Create SQS queue if it doesn't exist
    sqs = boto3.client('sqs')
    response = sqs.create_queue(
        QueueName='midori-queue',
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
        DBInstanceIdentifier='midori-db',
        MasterUsername='admin',
        MasterUserPassword='Admin123',
        DBInstanceClass='db.t2.micro',
        Engine='mysql',
        AllocatedStorage=20,
        DBName='midori',
        StorageType='gp2',
        BackupRetentionPeriod=7,
        MultiAZ=False,
        PubliclyAccessible=True,
        VpcSecurityGroupIds=[
            'sg-0c1e0b6c'
        ]
    )

    print(response)

def create_s3():
    # Create an S3 bucket if it doesn't exist
    s3 = boto3.client('s3')
    response = s3.create_bucket(
        Bucket='midori-bucket',
        CreateBucketConfiguration={
            'LocationConstraint': 'us-east-1'
        }
    )

    print(response)

create_sqs()
create_rds()
create_s3()