from chalice import Blueprint, BadRequestError
import json
import os
from .authorizers import admin_authorizer
from .connectHelper import create_connection
from .helpers import json_serial
from requests_toolbelt.multipart import decoder
import boto3

notification_service = Blueprint(__name__)
ses = boto3.client('ses')
sqs = boto3.client('sqs')
cognito_idp = boto3.client('cognito-idp')


def create_notification(itemId):
    # Create SQS message
    message = {
        'type': 'item',
        'id': itemId
    }

    # Send SQS message
    response = sqs.send_message(
        QueueUrl=os.environ.get('SQS_URL'),
        MessageBody=json.dumps(message)
    )


@notification_service.on_sqs_message(queue='reclaimit-queue', batch_size=5)
def handle_sqs_message(event):
    print("Hello world")
    for record in event:
        # Parse the record
        data = json.loads(record.body)
        print(data)

        type = data['type']
        id = data['id']

        # query item by id
        sql = "SELECT * FROM reclaimit.items WHERE id = %s"

        with create_connection().cursor() as cursor:
            cursor.execute(sql, (id))
            item = cursor.fetchone()

            print(json.dumps(item, default=json_serial))

            if item:
                categoryId = item['categoryId']
                # query notification subscribers based on categoryId
                sql = "SELECT * FROM reclaimit.notification_subscriptions WHERE categoryId = %s"

                with create_connection().cursor() as cursor:
                    cursor.execute(sql, (categoryId))
                    subscribers = cursor.fetchall()

                    print(json.dumps(subscribers, default=json_serial))

                    emails = []
                    if subscribers:
                        for subscriber in subscribers:
                            # query user by username
                            user = cognito_idp.admin_get_user(
                                UserPoolId=os.environ.get('USER_POOL_ID'),
                                Username=subscriber['username']
                            )

                            for attribute in user['UserAttributes']:
                                if attribute['Name'] == 'email':
                                    emails.append(attribute['Value'])
                                    break

                        print(emails)
                        # send email to users
                        response = ses.send_email(
                            Source=os.environ.get('SES_EMAIL'),
                            Destination={
                                'ToAddresses': emails
                            },
                            Message={
                                'Subject': {
                                    'Data': 'Reclaimit Notification'
                                },
                                'Body': {
                                    'Text': {
                                        'Data': 'New item added to category, here are the item details: \nName: ' + item['name'] + '\n Description: ' + item['description']
                                    }
                                }
                            }
                        )

                        for email in emails:
                            print('Email sent to: ' + email)
            else:
                return