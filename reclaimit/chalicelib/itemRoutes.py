from chalice import Blueprint, BadRequestError, Response
import json
from .authorizers import admin_authorizer
from .connectHelper import create_connection
from .helpers import json_serial
from requests_toolbelt.multipart import decoder
import boto3
from .notificationService import create_notification
import os
import traceback
import urllib.parse as urllib


item_routes = Blueprint(__name__)
s3 = boto3.client('s3')


@item_routes.route('/items', cors=True)
def get_items():
    sql = "SELECT *, category.name as categoryName FROM reclaimit.items INNER JOIN reclaimit.category ON reclaimit.items.categoryId = reclaimit.category.id"
    q = []
    limit = None
    if item_routes.current_request.query_params:
        categoryId = item_routes.current_request.query_params.get('categoryId')
        a = item_routes.current_request.query_params.get('attach')
        limit = item_routes.current_request.query_params.get('limit')

        if a:
            sql = "SELECT items.id, items.name, description, created_at, created_by, category.name as categoryName, min(ia.filename) as attachment FROM reclaimit.items INNER JOIN reclaimit.category ON reclaimit.items.categoryId = reclaimit.category.id LEFT JOIN reclaimit.itemAttachments ia ON reclaimit.items.id = ia.itemId"

        if categoryId:
            # SQL query to get all items except the created_by field
            q.append(categoryId)
            sql += " WHERE categoryId = %s"

        if a:
            sql += " GROUP BY items.id, items.name, description, created_at, created_by, categoryName"

        if limit:
            sql += " ORDER BY created_at DESC LIMIT " + limit

    if not limit:
        sql += " ORDER BY created_at DESC"

    with create_connection().cursor() as cursor:
        if len(q) > 0:
            cursor.execute(sql, q)
        else:
            cursor.execute(sql)

        result = cursor.fetchall()


        return json.loads(json.dumps(result, default=json_serial))


@item_routes.route('/admin/items', authorizer=admin_authorizer, cors=True, methods=['POST'])
def create_item():
    request = item_routes.current_request
    item = request.json_body

    # SQL query to insert a new item
    sql = "INSERT INTO reclaimit.items (name, description, categoryId, created_by) VALUES (%s, %s, %s, %s)"

    with create_connection().cursor() as cursor:
        # insert the new item and return the new item details
        cursor.execute(sql, (item['name'], item['description'], item['categoryId'], item_routes.current_request.context['authorizer']['principalId']))

        # get the last inserted item
        cursor.execute("SELECT * FROM reclaimit.items WHERE id = %s", (cursor.lastrowid))

        result = cursor.fetchone()

        create_notification(result['id'])
        return json.loads(json.dumps(result, default=json_serial))


@item_routes.route('/admin/items/{id}', cors=True, methods=['DELETE'], authorizer=admin_authorizer)
def delete_item(id):
    # SQL query to delete an item
    sql = "DELETE FROM reclaimit.items WHERE id = %s"

    with create_connection().cursor() as cursor:
        cursor.execute(sql, (id))

        # delete the attachments
        response = s3.list_objects_v2(
            Bucket=os.environ.get('S3_BUCKET'),
            Prefix=f'items/{id}/'
        )

        if 'Contents' in response:
            for obj in response['Contents']:
                s3.delete_object(
                    Bucket=os.environ.get('S3_BUCKET'),
                    Key=obj['Key']
                )

        return {'message': 'Item deleted successfully'}

@item_routes.route('/admin/items/today', authorizer=admin_authorizer, cors=True)
def get_items():
    # get today items
    sql = "SELECT *, category.name as categoryName FROM reclaimit.items INNER JOIN reclaimit.category ON reclaimit.items.categoryId = reclaimit.category.id WHERE created_at >= CURDATE()"

    with create_connection().cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchall()
        return json.loads(json.dumps(result, default=json_serial))


@item_routes.route('/items/{id}', cors=True)
def get_item(id):
    # SQL query to get all items except the created_by field
    sql = "SELECT *, category.name as categoryName FROM reclaimit.items INNER JOIN reclaimit.category ON reclaimit.items.categoryId = reclaimit.category.id WHERE reclaimit.items.id = %s"

    with create_connection().cursor() as cursor:
        cursor.execute(sql, (id))
        result = cursor.fetchone()
        return json.loads(json.dumps(result, default=json_serial))


@item_routes.route('/admin/items/{id}', authorizer=admin_authorizer, cors=True, methods=['PUT'])
def edit_item(id):
    request = item_routes.current_request
    body = request.json_body

    # Dynamically build the SQL query
    params = []
    sql = "UPDATE reclaimit.items SET "
    available_params = ["name", "description", "categoryId"]

    for key in available_params:
        if key in body:
            sql += key + " = %s, "
            params.append(body[key])

    sql = sql[:-2] + " WHERE id = %s"
    params.append(id)

    getSql = "SELECT * FROM reclaimit.items WHERE id = %s"

    try:
        with create_connection().cursor() as cursor:
            cursor.execute(sql, params)
            cursor.execute(getSql, id)
            task = cursor.fetchone()

            return {"message": "Item updated successfully!"}
    except Exception as e:
        raise BadRequestError(str(e))


@item_routes.route('/categories', cors=True)
def get_categories():
    # SQL query to get all items except the created_by field
    sql = "SELECT * FROM reclaimit.category"

    with create_connection().cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchall()
        return json.loads(json.dumps(result, default=json_serial))


@item_routes.route('/items/{id}/attachments', cors=True)
def get_item_attachments(id):
    attachments = get_attachments(id)
    return attachments


@item_routes.route('/admin/items/{id}/attachments', cors=True, methods=['POST'], content_types=['multipart/form-data'], authorizer=admin_authorizer)
def upload_item_attachment(id):
    request = item_routes.current_request
    body = request.raw_body

    # decode the multipart form data
    d = decoder.MultipartDecoder(body, request.headers['content-type'])
    file = None
    filename = None

    part = d.parts[1]
    if part.headers[b'Content-Disposition']:
        filename = part.headers[b'Content-Disposition'].decode('utf-8').split('filename=')[1].strip('"')

        file = part.content

    if not file or not filename:
        raise BadRequestError('File not found in request')

    # upload the file to S3
    s3.put_object(
        Bucket=os.environ.get('S3_BUCKET'),
        Key=f'items/{id}/{filename}',
        Body=file
    )

    sql = "INSERT INTO reclaimit.itemAttachments (itemId, filename) VALUES (%s, %s)"

    with create_connection().cursor() as cursor:
        cursor.execute(sql, (id, filename))

    return {'message': 'File uploaded successfully'}

@item_routes.route('/items/{id}/attachments/{filename}', cors=True)
def get_task_attachment(id, filename):
    filename = urllib.unquote(filename)
    try:
        response = s3.get_object(
            Bucket=os.environ.get('S3_BUCKET'),
            Key="items/" + id + "/" + filename
        )
    except Exception as e:
        traceback.print_exc()
        raise BadRequestError("Error fetching attachment")

    return Response(body=response['Body'].read(), headers={'Content-Type': response['ContentType']})

def get_attachments(item_id):
    response = s3.list_objects_v2(
        Bucket=os.environ.get('S3_BUCKET'),
        Prefix=f'items/{item_id}/'
    )

    attachments = []
    if 'Contents' in response:
        for obj in response['Contents']:
            # remove the folder name from the list of attachments
            obj['Key'] = obj['Key'].replace(f'items/{item_id}/', '')
            attachments.append(obj['Key'])

    # remove the first element which is the folder itself
    if len(attachments) < 0:
        attachments.pop(0)

    return attachments