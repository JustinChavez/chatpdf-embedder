import boto3
import os
from decouple import config
from botocore.exceptions import ClientError
import re

def download_folder_contents_from_s3(bucket_name, prefix, folder_name):

    s3 = boto3.client(
        's3',
        aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY')
    )

    # Check if the folder exists in S3
    s3_path = os.path.join(prefix, folder_name)

    # Get the local path to download the files to
    local_path = os.path.join(prefix, folder_name)

    # Create the local directory if it doesn't exist
    os.makedirs(local_path, exist_ok=True)

    # Get a list of all the objects in the S3 folder
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)
    if 'Contents' not in response:
        raise ValueError(f"Error: The index {folder_name} does not exist")

    # Download each object to the local directory
    for obj in response['Contents']:
        key = obj['Key']
        filename = os.path.basename(key)
        local_file_path = os.path.join(local_path, filename)
        s3.download_file(bucket_name, key, local_file_path)
        # print(f"{key} downloaded to {local_file_path}")

def check_if_folder_exists(bucket_name, prefix, folder_name):

    s3 = boto3.client(
        's3',
        aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY')
    )

    # Hardcode finding index.faiss for now. Unable to detect folders otherwise
    s3_path = os.path.join(prefix, folder_name, "index.faiss")
    try:
        # print(s3.head_object(Bucket=bucket_name, Key=s3_path))
        # print(f"The directory '{s3_path}' exists in the '{bucket_name}' bucket.")
        return True
    except ClientError:
        # print(f"The directory '{s3_path}' does not exist in the '{bucket_name}' bucket.")
        return False
    
def is_valid_input(var):
    """
    Checks if a variable only contains alphanumerics, underscores, and hyphens.
    
    Args:
        var (str): The variable to check.
        
    Returns:
        bool: True if the variable only contains alphanumerics, underscores, and hyphens,
              False otherwise.
    """
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, var))