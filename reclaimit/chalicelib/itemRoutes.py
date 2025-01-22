from chalice import Blueprint
import json
from .authorizers import admin_authorizer
from .connectHelper import create_connection
from .helpers import json_serial

item_routes = Blueprint(__name__)

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