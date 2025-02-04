# ReclaimIt Backend

## Description
This is the backend for the ReclaimIt project. It is a RESTful API that allows users to create, read, update, and delete found items and categories. It also allows users to create, read, update, and delete users. The API is built using the AWS Chalice framework and is deployed on AWS Lambda.

## Installation
1. Clone the repository
2. Open project in your favorite IDE before the reclaimit directory (right here, this location)
3. Open terminal and navigate to the project directory (cd reclaimit)
4. Run `pip install -r requirements.txt` to install dependencies
5. Refer to `deployer.py` for deployment instructions
6. Use `chalice local` to run the server locally
7. Use `chalice deploy` to deploy the server to AWS Lambda