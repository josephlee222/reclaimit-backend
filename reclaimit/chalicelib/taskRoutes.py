from chalice import Blueprint, BadRequestError, ForbiddenError, Response
import boto3
from .authorizers import farmer_authorizer, farm_manager_authorizer
from .connectHelper import create_connection
import json

task_routes = Blueprint(__name__)
s3 = boto3.client('s3')

# Get all tasks from the database
@task_routes.route('/tasks/list/{display}', authorizer=farm_manager_authorizer, cors=True)
def get_all_tasks(display):
    sql = ""
    if display == 'my':
        sql = """
                SELECT t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status, t.priority,
                       COALESCE(ta_count.users_assigned, 0) as users_assigned
                FROM Tasks as t
                LEFT JOIN (
                    SELECT ta.taskId, COUNT(ta.id) as users_assigned
                    FROM TasksAssignees AS ta
                    GROUP BY ta.taskId
                ) ta_count ON t.id = ta_count.taskId
                LEFT JOIN TasksAssignees AS ta ON t.id = ta.taskId
                WHERE ta.username = %s AND t.hidden = 0
                GROUP BY t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status
                ORDER BY t.priority ASC
            """
    elif display == 'all':
        sql = "SELECT t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status, t.priority, count(ta.id) as users_assigned FROM Tasks as t LEFT JOIN TasksAssignees AS ta ON t.id = ta.taskId GROUP BY t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status ORDER BY t.priority ASC"
    elif display == 'hidden':
        sql = "SELECT t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status, t.priority, count(ta.id) as users_assigned FROM Tasks as t LEFT JOIN TasksAssignees AS ta ON t.id = ta.taskId WHERE t.hidden = 0 GROUP BY t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status ORDER BY t.priority ASC"
    elif display == 'outstanding':
        sql = """
            SELECT t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status, t.priority,
                   COALESCE(ta_count.users_assigned, 0) as users_assigned
            FROM Tasks as t
            LEFT JOIN (
                SELECT ta.taskId, COUNT(ta.id) as users_assigned
                FROM TasksAssignees AS ta
                GROUP BY ta.taskId
            ) ta_count ON t.id = ta_count.taskId
            LEFT JOIN TasksAssignees AS ta ON t.id = ta.taskId
            WHERE ta.username = %s AND t.hidden = 0 AND t.status = 1
            GROUP BY t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status
            ORDER BY t.priority ASC
            LIMIT 3;
        """

    with create_connection().cursor() as cursor:
        if display == 'my' or display == 'outstanding':
            cursor.execute(sql, task_routes.current_request.context['authorizer']['principalId'])
        else:
            cursor.execute(sql)

        result = cursor.fetchall()
        return json.loads(json.dumps(result, default=str))


@task_routes.route('/tasks/{id}', authorizer=farmer_authorizer, cors=True)
def get_task(id):
    sql = "SELECT t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status, t.priority, t.hidden, count(ta.id) as users_assigned FROM Tasks as t LEFT JOIN TasksAssignees AS ta ON t.id = ta.taskId WHERE t.id = %s GROUP BY t.id, t.title, t.description, t.created_at, t.updated_at, t.created_by, t.status"
    assignee_sql = "SELECT username, email FROM TasksAssignees WHERE taskId = %s"

    with create_connection().cursor() as cursor:
        cursor.execute(sql, id)
        taskResult = cursor.fetchone()

        cursor.execute(assignee_sql, id)
        assigneeResult = cursor.fetchall()

        return json.loads(json.dumps({'task': taskResult, 'assignees': assigneeResult}, default=str))


@task_routes.route('/tasks/{id}', authorizer=farm_manager_authorizer, cors=True, methods=['DELETE'])
def delete_task(id):
    sql = "DELETE FROM Tasks WHERE id = %s"

    with create_connection().cursor() as cursor:
        cursor.execute(sql, id)
        return {"message": "Task deleted successfully!"}

@task_routes.route('/tasks/{id}', authorizer=farm_manager_authorizer, cors=True, methods=['PUT'])
def edit_task(id):
    request = task_routes.current_request
    body = request.json_body

    # Dynamically build the SQL query
    params = []
    sql = "UPDATE Tasks SET "
    available_params = ["title", "description", "priority", "status", "hidden"]

    for key in available_params:
        if key in body:
            sql += key + " = %s, "
            params.append(body[key])

    sql = sql[:-2] + " WHERE id = %s"
    params.append(id)

    try:
        with create_connection().cursor() as cursor:
            cursor.execute(sql, params)
            return {"message": "Task updated successfully!"}
    except Exception as e:
        return BadRequestError(str(e))


@task_routes.route('/tasks/{id}/status', authorizer=farmer_authorizer, cors=True, methods=['PUT'])
def update_task_status(id):
    request = task_routes.current_request
    body = request.json_body

    status = body["status"]

    sql = "UPDATE Tasks SET status = %s WHERE id = %s"

    # Check if the user is assigned to the task or if the user is the creator of the task
    check_sql = "SELECT * FROM TasksAssignees WHERE taskId = %s AND username = %s"

    with create_connection().cursor() as cursor:
        cursor.execute(check_sql, (id, task_routes.current_request.context['authorizer']['principalId']))
        result = cursor.fetchone()

        if not result:
            return ForbiddenError("You are not authorized to update the status of this task")
        cursor.execute(sql, (status, id))
        return {"message": "Task status updated successfully!"}

@task_routes.route('/tasks/{id}/attachments', authorizer=farmer_authorizer, cors=True)
def get_task_attachments(id):
    attachments = get_attachments(id)
    return attachments


@task_routes.route('/tasks/{id}/attachments/{filename}', authorizer=farmer_authorizer, cors=True)
def get_task_attachment(id, filename):
    try:
        response = s3.get_object(
            Bucket='midori-bucket',
            Key=f'tasks/{id}/{filename}'
        )
    except Exception as e:
        raise BadRequestError("Error fetching attachment")

    return Response(body=response['Body'].read(), headers={'Content-Type': response['ContentType']})


@task_routes.route('/tasks', authorizer=farm_manager_authorizer, cors=True, methods=['POST'])
def create_task():
    request = task_routes.current_request
    body = request.json_body

    title = body["title"]
    description = body["description"]
    priority = body["priority"]

    sql = "INSERT INTO Tasks (title, description, priority, created_by) VALUES (%s, %s, %s, %s)"

    with create_connection().cursor() as cursor:
        cursor.execute(sql, (title, description, priority, task_routes.current_request.context['authorizer']['principalId']))
        return {"message": "Task created successfully!"}


def get_attachments(task_id):
    response = s3.list_objects_v2(
        Bucket='midori-bucket',
        Prefix=f'tasks/{task_id}/'
    )

    attachments = []
    if 'Contents' in response:
        for obj in response['Contents']:
            # remove the folder name from the list of attachments
            obj['Key'] = obj['Key'].replace(f'tasks/{task_id}/', '')
            attachments.append(obj['Key'])

    # remove the first element which is the folder itself
    if len(attachments) > 0:
        attachments.pop(0)

    return attachments
