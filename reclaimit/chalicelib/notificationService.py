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


@notification_service.route('/subscriptions', cors=True, methods=['GET'])
def get_subscriptions():
    if notification_service.current_request.query_params:
        email = notification_service.current_request.query_params.get('email')

        if email:
            sql = "SELECT * FROM notification_subscriptions WHERE email = %s"
            with create_connection().cursor() as cursor:
                cursor.execute(sql, (email))
                result = cursor.fetchall()

                return json.loads(json.dumps(result, default=json_serial))
        else:
            raise BadRequestError("Missing required parameters email")
    else:
        raise BadRequestError("Missing required parameters email")


@notification_service.route('/subscriptions', cors=True, methods=['POST'])
def create_subscription():
    if notification_service.current_request.query_params:
        email = notification_service.current_request.query_params.get('email')

        if email:
            body = notification_service.current_request.json_body
            categoryIds = body['categoryIds']

            with create_connection().cursor() as cursor:
                # Delete existing subscriptions
                del_sql = "DELETE FROM notification_subscriptions WHERE email = %s"
                cursor.execute(del_sql, (email))

                # Insert new subscriptions
                for categoryId in categoryIds:
                    sql = "INSERT INTO notification_subscriptions (email, categoryId) VALUES (%s, %s)"
                    cursor.execute(sql, (email, categoryId))

            sql = "SELECT * FROM reclaimit.email_verifications WHERE email = %s"

            with create_connection().cursor() as cursor:
                cursor.execute(sql, (email))
                result = cursor.fetchone()

                with create_connection().cursor() as cursor:
                    if result:
                        sql = "DELETE FROM email_verifications WHERE email = %s"
                        cursor.execute(sql, (email))

                    recreate_sql = "INSERT INTO email_verifications (email, token) VALUES (%s, %s)"
                    token = os.urandom(16).hex()
                    cursor.execute(recreate_sql, (email, token))

                    # Send email verification
                    response = ses.send_email(
                        Source=os.environ.get('SES_EMAIL'),
                        Destination={
                            'ToAddresses': [email]
                        },
                        Message={
                            'Subject': {
                                'Data': 'Reclaimit Email Verification'
                            },
                            'Body': {
                                'Text': {
                                    'Data': 'Please verify your email by pasting the code below in the Reclaimit website: \n\n' + token
                                }
                            }
                        }
                    )

                    return json.loads(json.dumps({'message': 'Email verification sent'}, default=json_serial))
        else:
            raise BadRequestError("Missing required parameters email")
    else:
        raise BadRequestError("Missing required parameters email")


@notification_service.route('/subscriptions/verify', cors=True, methods=['GET'])
def verify_subscription():
    if notification_service.current_request.query_params:
        email = notification_service.current_request.query_params.get('email')
        token = notification_service.current_request.query_params.get('token')

        if email and token:
            sql = "SELECT * FROM email_verifications WHERE email = %s AND token = %s"

            with create_connection().cursor() as cursor:
                cursor.execute(sql, (email, token))
                result = cursor.fetchone()

                if result:
                    # Set email as verified
                    sql = "UPDATE reclaimit.email_verifications SET verified = 1 WHERE email = %s"
                    with create_connection().cursor() as cursor:
                        cursor.execute(sql, (email))

                    return json.loads(json.dumps({'message': 'Email verified'}, default=json_serial))
                else:
                    raise BadRequestError("Invalid token")
        else:
            raise BadRequestError("Missing required parameters email")
    else:
        raise BadRequestError("Missing required parameters email")


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
        sql = "SELECT * FROM items WHERE id = %s"

        with create_connection().cursor() as cursor:
            cursor.execute(sql, (id))
            item = cursor.fetchone()

            print(json.dumps(item, default=json_serial))

            if item:
                categoryId = item['categoryId']
                # query notification subscribers based on categoryId
                sql = '''SELECT notification_subscriptions.email FROM notification_subscriptions
                INNER JOIN email_verifications ON notification_subscriptions.email = email_verifications.email
                WHERE categoryId = %s AND verified = 1'''

                with create_connection().cursor() as cursor:
                    cursor.execute(sql, (categoryId))
                    subscribers = cursor.fetchall()

                    print(json.dumps(subscribers, default=json_serial))

                    emails = []
                    if subscribers:
                        for subscriber in subscribers:
                            # query user by username
                            emails.append(subscriber['email'])

                        print(emails)
                        # send email to users
                        response = ses.send_email(
                            Source=os.environ.get('SES_EMAIL'),
                            Destination={
                                'ToAddresses': emails
                            },
                            Message={
                                'Subject': {
                                    'Data': 'Reclaimit Notification - New Item Added'
                                },
                                'Body': {
                                    'Text': {
                                        'Data': 'New item added to category, here are the item details: \nName: ' + item['name'] + '\nDescription: ' + item['description'] + "\n\n Please check the Reclaimit website for more details."
                                    }
                                }
                            }
                        )

                        for email in emails:
                            print('Email sent to: ' + email)
            else:
                return