from chalice import Blueprint, BadRequestError
import json
from .authorizers import admin_authorizer
from .connectHelper import create_connection
from .helpers import json_serial
from requests_toolbelt.multipart import decoder
import boto3

item_routes = Blueprint(__name__)
s3 = boto3.client('s3')

@item_routes.route('/admin/items', authorizer=admin_authorizer, cors=True)
def get_items():
    if item_routes.current_request.query_params:
        categoryId = item_routes.current_request.query_params.get('categoryId')

        if categoryId:
            # SQL query to get all items except the created_by field
            sql = "SELECT * FROM reclaimit.items WHERE categoryId = %s"
            with create_connection().cursor() as cursor:
                cursor.execute(sql, (categoryId))
                result = cursor.fetchall()
                return json.loads(json.dumps(result, default=json_serial))

    sql = "SELECT * FROM reclaimit.items"

    with create_connection().cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchall()
        return json.loads(json.dumps(result, default=json_serial))


@item_routes.route('/admin/items', authorizer=admin_authorizer, cors=True, methods=['POST'])
def create_item():
    request = item_routes.current_request
    item = request.json_body

    # SQL query to insert a new item
    sql = "INSERT INTO reclaimit.items (name, description, categoryId) VALUES (%s, %s, %s)"

    with create_connection().cursor() as cursor:
        # insert the new item and return the new item details
        cursor.execute(sql, (item['name'], item['description'], item['categoryId']))

        # get the last inserted item
        cursor.execute("SELECT * FROM reclaimit.items WHERE id = %s", (cursor.lastrowid))

        result = cursor.fetchone()
        return json.loads(json.dumps(result, default=json_serial))

@item_routes.route('/admin/items/today', authorizer=admin_authorizer, cors=True)
def get_items():
    # get today items
    sql = "SELECT * FROM reclaimit.items WHERE created_at >= CURDATE()"

    with create_connection().cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchall()
        return json.loads(json.dumps(result, default=json_serial))

@item_routes.route('/items', cors=True)
def get_items_guest():
    if item_routes.current_request.query_params:
        categoryId = item_routes.current_request.query_params.get('categoryId')

        if categoryId:
            # SQL query to get all items except the created_by field
            sql = "SELECT id, name, description, created_at, categoryId, created_at FROM reclaimit.items WHERE categoryId = %s"
            with create_connection().cursor() as cursor:
                cursor.execute(sql, (categoryId))
                result = cursor.fetchall()
                return json.loads(json.dumps(result, default=json_serial))

    # SQL query to get all items except the created_by field
    sql = "SELECT id, name, description, created_at, categoryId, created_at FROM reclaimit.items"

    with create_connection().cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchall()
        return json.loads(json.dumps(result, default=json_serial))

@item_routes.route('/items/{id}', cors=True)
def get_item(id):
    # SQL query to get all items except the created_by field
    sql = "SELECT * FROM reclaimit.items INNER JOIN reclaimit.category ON reclaimit.items.categoryId = reclaimit.category.id WHERE reclaimit.items.id = %s"

    with create_connection().cursor() as cursor:
        cursor.execute(sql, (id))
        result = cursor.fetchall()
        return json.loads(json.dumps(result, default=json_serial))

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
        Bucket='reclaimit-bucket',
        Key=f'items/{id}/{filename}',
        Body=file
    )

    return {'message': 'File uploaded successfully'}

def get_attachments(item_id):
    response = s3.list_objects_v2(
        Bucket='reclaimit-bucket',
        Prefix=f'items/{item_id}/'
    )

    attachments = []
    if 'Contents' in response:
        for obj in response['Contents']:
            # remove the folder name from the list of attachments
            obj['Key'] = obj['Key'].replace(f'items/{item_id}/', '')
            attachments.append(obj['Key'])

    # remove the first element which is the folder itself
    if len(attachments) > 0:
        attachments.pop(0)

    return attachments