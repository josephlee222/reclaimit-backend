from chalice import Blueprint
import boto3
import json
from .authorizers import admin_authorizer
import pymysql
from .connectHelper import create_connection

item_routes = Blueprint(__name__)

@item_routes.route('/farms', authorizer=admin_authorizer, cors=True)
def get_farms():
    sql = "SELECT * FROM `Farms`"

    with create_connection().cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchall()
        return result